"""Гибридный конвейер проверки отчёта (LangGraph).

Стратегия комбинирования — каскадная с арбитражем:

    нормализация → продукционные правила ─(BLOCK)→ отклонить
                                         └→ SimHash-фильтр ─(дубликат)→ отклонить
                                                           └→ описание изображений (VLM)
                                                              → 3 LLM-оценщика (параллельно)
                                                               → символьная агрегация
                                                                  ├→ принять
                                                                  ├→ ручная проверка
                                                                  └→ отклонить → пояснение (LLM)

Дешёвые детерминированные проверки выполняются первыми и отсекают заведомо
неприемлемые отчёты без обращения к языковой модели; языковая модель
оценивает смысловое соответствие; итоговое решение и разрешение
противоречий выполняются символьным агрегатором. Каждый шаг записывается
в протокол, который хранится вместе с отчётом.

Режимы (для сравнительного эксперимента):
  hybrid   — полный конвейер;
  symbolic — только правила и SimHash (решение без языковой модели);
  neural   — только ансамбль оценщиков с голосованием большинством.
"""
from __future__ import annotations

import operator
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Protocol, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

import asyncio

from common.documents import (MARKER_RE, ReportImage, image_captions, image_priority, insert_descriptions,
                              strip_markers, strip_title_page)
from llm.chat import ainvoke_text, split_model
from models.enums import VerificationDecision
from settings import llm_settings, verification_settings as cfg, vision_settings
from .images import describe_images
from .lab_match import match_lab
from .aggregation import aggregate, majority_vote
from .judges import REPORT_CHARS_FOR_LLM, JudgeVerdict, run_judge
from .normalizer import TextNormalizer
from .prompts import FEEDBACK_SYSTEM, FEEDBACK_USER
from .rules import LabRequirements, Outcome, apply_rules, build_facts
from .simhash import simhash_bits

MODES = ("hybrid", "symbolic", "neural")


class FingerprintIndex(Protocol):
    def find_nearest(self, bits: list[int], *, lab_id: int, exclude_student_id: int): ...


class State(TypedDict, total=False):
    mode: str
    text: str                 # текст без маркеров изображений (правила, SimHash, пояснение)
    marked_text: str          # текст с маркерами ⟦img:N⟧
    images: list
    judge_text: str           # текст для оценщиков: маркеры заменены описаниями рисунков
    requirements: LabRequirements
    student_id: int
    lab_id: int
    lemmas: list[str]
    facts: Any
    rule_results: list[dict]
    blocked: bool
    topic_doubt: bool
    lab_doubt: bool
    fingerprint: list[int]
    nearest: dict | None
    duplicate: bool
    verdicts: Annotated[list[JudgeVerdict], operator.add]
    aggregation: dict
    decision: str
    decided_by: str
    reason: str
    feedback: str
    protocol: Annotated[list[dict], operator.add]
    llm_calls: Annotated[int, operator.add]
    vision_calls: int
    image_descriptions: list[dict]


@dataclass
class VerificationResult:
    decision: VerificationDecision
    decided_by: str           # rules | simhash | judges | symbolic | neural
    reason: str
    feedback: str
    score: float | None
    max_similarity: float | None
    nearest_report_id: int | None
    fingerprint: list[int]
    protocol: list[dict] = field(default_factory=list)
    llm_calls: int = 0
    duration_ms: int = 0
    verdicts: list[dict] = field(default_factory=list)
    vision_calls: int = 0
    image_descriptions: list[dict] = field(default_factory=list)


def _step(order: int, title: str, component: str, kind: str, status: str,
          details: dict, started: float) -> dict:
    return {
        "order": order, "title": title, "component": component, "kind": kind,
        "status": status, "details": details,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }


class VerificationPipeline:
    def __init__(self, index: FingerprintIndex, mode: str = "hybrid") -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.index = index
        self.mode = mode
        self.graph = self._build()

    # ── узлы графа ───────────────────────────────────────────────────────────
    async def _normalize(self, state: State) -> dict:
        t0 = time.perf_counter()
        def work():
            normalizer = TextNormalizer()
            lemmas = normalizer.lemmas(state["text"])
            task_lemmas = normalizer.lemmas(state["requirements"].task)
            return lemmas, build_facts(state["text"], lemmas, task_lemmas)

        # лемматизация — вычисления на процессоре: в отдельном потоке, чтобы не блокировать
        # цикл событий сервера (другие запросы во время проверки)
        lemmas, facts = await asyncio.to_thread(work)
        return {
            "lemmas": lemmas, "facts": facts,
            "protocol": [_step(1, "Нормализация текста", "Лемматизатор Natasha", "symbolic", "info", {
                "words": facts.word_count, "lemmas": len(lemmas),
                "task_terms": facts.task_terms[:12],
            }, t0)],
        }

    async def _rules(self, state: State) -> dict:
        t0 = time.perf_counter()
        results = apply_rules(state["facts"], state["requirements"])
        blocked = any(r.outcome is Outcome.BLOCK for r in results)
        topic_doubt = any(r.rule_id == "R6" and r.outcome is Outcome.WARN for r in results)
        status = "fail" if blocked else "warn" if any(r.outcome is Outcome.WARN for r in results) else "pass"
        return {
            "rule_results": [r.to_dict() for r in results], "blocked": blocked, "topic_doubt": topic_doubt,
            "protocol": [_step(2, "Продукционные правила", "База правил формальных требований",
                               "symbolic", status, {"rules": [r.to_dict() for r in results]}, t0)],
        }

    async def _simhash(self, state: State) -> dict:
        t0 = time.perf_counter()
        bits = simhash_bits(state["lemmas"], bits=cfg.simhash_bits, k=cfg.simhash_shingle)
        nearest = await asyncio.to_thread(self.index.find_nearest, bits, lab_id=state["lab_id"],
                                          exclude_student_id=state["student_id"])
        nearest_d = None
        duplicate = False
        if nearest is not None:
            similarity = round(1 - nearest.hamming / cfg.simhash_bits, 3)
            duplicate = nearest.hamming <= cfg.duplicate_max_hamming
            nearest_d = {"report_id": nearest.report_id, "hamming": nearest.hamming,
                         "similarity": similarity}
        return {
            "fingerprint": bits, "nearest": nearest_d, "duplicate": duplicate,
            "protocol": [_step(3, "Проверка на заимствования (SimHash)", "Индекс отпечатков Weaviate",
                               "symbolic", "fail" if duplicate else "pass", {
                                   "nearest": nearest_d,
                                   "max_hamming": cfg.duplicate_max_hamming,
                                   "bits": cfg.simhash_bits,
                                   "fingerprint_hex": f"{int(''.join(map(str, bits)), 2):0{cfg.simhash_bits // 4}x}",
                               }, t0)],
        }

    def _judge_node(self, judge: str, order: int):
        async def node(state: State) -> dict:
            t0 = time.perf_counter()
            verdict = await run_judge(judge, state["requirements"].task,
                                      state.get("judge_text") or state["text"])
            status = "info" if verdict.valid else "fail"
            return {
                "verdicts": [verdict], "llm_calls": 1,
                "protocol": [_step(order, verdict.title, "Языковая модель", "neural", status,
                                   verdict.to_dict(), t0)],
            }
        return node

    async def _describe(self, state: State) -> dict:
        """Описание изображений моделью зрения и вставка описаний на место рисунков.

        Перед отправкой во внешние модели удаляется титульный лист (ФИО, группа,
        преподаватель) вместе с рисунками на нём.
        """
        marked = strip_title_page(state.get("marked_text") or state["text"])
        present = {int(m) for m in MARKER_RE.findall(marked)}
        images = [img for img in (state.get("images") or []) if img.index in present]
        if not images or not vision_settings.enabled:
            return {"judge_text": strip_markers(marked)}
        t0 = time.perf_counter()
        captions = image_captions(marked)
        descriptions, skipped = await describe_images(
            images, {i: image_priority(c) for i, c in captions.items()})
        found = {d.index: d.description for d in descriptions if d.valid}
        calls = sum(1 for d in descriptions if d.api_call)
        failed = sum(1 for d in descriptions if not d.valid)
        status = "info" if found or not descriptions else "warn"
        details = [{**d.to_dict(), "caption": captions.get(d.index, "")} for d in descriptions]
        return {
            "judge_text": insert_descriptions(marked, found),
            "image_descriptions": details,
            "vision_calls": calls,
            "protocol": [_step(4, "Описание изображений", "Модель зрения (VLM)", "neural", status, {
                "model": vision_settings.model, "images": len(images), "described": len(found),
                "cached": sum(1 for d in descriptions if d.cached), "failed": failed,
                "skipped_by_limit": skipped, "max_images": vision_settings.max_images,
                "descriptions": details,
            }, t0)],
        }

    async def _lab_match(self, state: State) -> dict:
        """R7: ближе ли отчёт к своей лабораторной, чем к другим работам курса (векторы)."""
        t0 = time.perf_counter()
        req = state["requirements"]
        if not cfg.lab_match_enabled:
            return {"lab_doubt": False}
        text = strip_title_page(state["text"])
        res = await asyncio.to_thread(match_lab, text, req.task, req.other_tasks)
        status = "warn" if res.doubt else "pass" if res.checked else "info"
        return {
            "lab_doubt": res.doubt,
            "protocol": [_step(3.5, "Соответствие лабораторной работе (R7)", "Эмбеддинги и правило порогов",
                               "symbolic", status, {"lab_match": res.to_dict()}, t0)],
        }

    async def _aggregate(self, state: State) -> dict:
        t0 = time.perf_counter()
        verdicts = sorted(state.get("verdicts", []), key=lambda v: v.judge)
        if self.mode == "neural":
            decision = majority_vote(verdicts)
            agg = {"decision": decision.value, "rule": "majority",
                   "reason": "Голосование большинством (вариант без символьных компонентов)"}
        else:
            res = aggregate(verdicts, topic_doubt=state.get("topic_doubt", False) or state.get("lab_doubt", False))
            agg = res.to_dict()
            decision = res.decision
        return {
            "aggregation": agg, "decision": decision.value, "decided_by": "judges",
            "reason": agg["reason"],
            "protocol": [_step(8, "Агрегация вердиктов", "Символьный арбитр", "symbolic",
                               {"approve": "pass", "reject": "fail"}.get(decision.value, "warn"), agg, t0)],
        }

    async def _feedback(self, state: State) -> dict:
        t0 = time.perf_counter()
        findings = []
        for v in state.get("verdicts", []):
            if not v.valid:
                continue
            findings.append(f"{v.title}: {v.summary}")
            for c in v.criteria:
                if c.get("met") is False:
                    findings.append(f"  - {c.get('name')}: {c.get('comment')}")
        messages = [
            SystemMessage(content=FEEDBACK_SYSTEM),
            HumanMessage(content=FEEDBACK_USER.format(
                requirements=state["requirements"].task,
                findings="\n".join(findings) or "нет данных",
                report=strip_title_page(state["text"])[:4000])),
        ]
        try:
            name, thinking = split_model(llm_settings.feedback_model)
            text = (await ainvoke_text(messages, temperature=0.3, max_tokens=700,
                                       model=name, thinking=thinking)).strip()
            calls = 1
        except Exception as exc:
            text = "Отчёт не соответствует требованиям задания. " + "; ".join(findings[:4])
            calls = 0
            findings.append(f"(пояснение сформировано без LLM: {type(exc).__name__})")
        return {
            "feedback": text, "llm_calls": calls,
            "protocol": [_step(9, "Пояснение для студента", "Языковая модель", "neural", "info",
                               {"length": len(text)}, t0)],
        }

    async def _finalize_rules(self, state: State) -> dict:
        failed = [r for r in state["rule_results"] if r["outcome"] == Outcome.BLOCK.value]
        lines = [f"• {r['title']}: {r['message']}" for r in failed]
        return {"decision": VerificationDecision.REJECT.value, "decided_by": "rules",
                "reason": "Не выполнены формальные требования",
                "feedback": "Отчёт отклонён автоматически, так как не выполнены формальные требования:\n"
                            + "\n".join(lines)}

    async def _finalize_duplicate(self, state: State) -> dict:
        n = state["nearest"]
        return {"decision": VerificationDecision.REJECT.value, "decided_by": "simhash",
                "reason": f"Сходство с другим отчётом {n['similarity']:.0%}",
                "feedback": "Отчёт отклонён: текст практически совпадает с отчётом другого студента "
                            f"по этой лабораторной (сходство {n['similarity']:.0%}). "
                            "Подготовьте отчёт самостоятельно."}

    async def _finalize_symbolic(self, state: State) -> dict:
        doubt = state.get("topic_doubt", False)
        decision = VerificationDecision.REJECT if doubt else VerificationDecision.APPROVE
        return {"decision": decision.value, "decided_by": "symbolic",
                "reason": "Правило R6: отчёт не по теме" if doubt else "Формальные проверки пройдены",
                "feedback": ""}

    async def _finalize(self, state: State) -> dict:
        decision = state["decision"]
        if decision == VerificationDecision.MANUAL_REVIEW.value:
            return {"feedback": "Автоматическая проверка не дала однозначного результата. "
                                "Отчёт передан преподавателю для ручной проверки."}
        if decision == VerificationDecision.APPROVE.value:
            return {"feedback": "Отчёт прошёл автоматическую проверку и передан преподавателю."}
        return {}

    # ── маршрутизация ───────────────────────────────────────────────────────
    def _route_start(self, state: State) -> str:
        return ["describe", "lab_match"] if self.mode == "neural" else "normalize"

    def _route_rules(self, state: State) -> str:
        return "reject_rules" if state["blocked"] else "simhash"

    def _route_simhash(self, state: State):
        if state["duplicate"]:
            return "reject_duplicate"
        if self.mode == "symbolic":
            return "finalize_symbolic"
        return ["describe", "lab_match"]

    def _route_aggregate(self, state: State) -> str:
        if state["decision"] == VerificationDecision.REJECT.value and self.mode == "hybrid":
            return "feedback"
        return "finalize"

    def _build(self):
        g = StateGraph(State)
        g.add_node("normalize", self._normalize)
        g.add_node("rules", self._rules)
        g.add_node("simhash", self._simhash)
        g.add_node("judge_strict", self._judge_node("strict", 5))
        g.add_node("judge_objective", self._judge_node("objective", 6))
        g.add_node("judge_loyal", self._judge_node("loyal", 7))
        g.add_node("describe", self._describe)  # общая точка входа ветви оценщиков
        g.add_node("lab_match", self._lab_match)
        g.add_node("aggregate", self._aggregate)
        g.add_node("feedback", self._feedback)
        g.add_node("reject_rules", self._finalize_rules)
        g.add_node("reject_duplicate", self._finalize_duplicate)
        g.add_node("finalize_symbolic", self._finalize_symbolic)
        g.add_node("finalize", self._finalize)

        g.add_conditional_edges(START, self._route_start, ["normalize", "describe", "lab_match"])
        g.add_edge("normalize", "rules")
        g.add_conditional_edges("rules", self._route_rules, ["reject_rules", "simhash"])
        g.add_conditional_edges("simhash", self._route_simhash,
                                ["reject_duplicate", "finalize_symbolic", "describe", "lab_match"])
        for j in ("judge_strict", "judge_objective", "judge_loyal"):
            g.add_edge("describe", j)
        # арбитр ждёт и оценщиков, и правило R7 (выполняется параллельно с описанием рисунков)
        g.add_edge(["judge_strict", "judge_objective", "judge_loyal", "lab_match"], "aggregate")
        g.add_conditional_edges("aggregate", self._route_aggregate, ["feedback", "finalize"])
        g.add_edge("feedback", "finalize")
        for terminal in ("reject_rules", "reject_duplicate", "finalize_symbolic", "finalize"):
            g.add_edge(terminal, END)
        return g.compile()

    # ── запуск ──────────────────────────────────────────────────────────────
    async def run(self, *, text: str, requirements: LabRequirements, student_id: int,
                  lab_id: int, images: list[ReportImage] | None = None) -> VerificationResult:
        """text может содержать маркеры ⟦img:N⟧ мест рисунков (см. common.documents)."""
        started = time.perf_counter()
        state: State = await self.graph.ainvoke({
            "mode": self.mode, "text": strip_markers(text or ""), "marked_text": text or "",
            "images": images or [], "requirements": requirements,
            "student_id": student_id, "lab_id": lab_id,
            "verdicts": [], "protocol": [], "llm_calls": 0,
        })
        protocol = sorted(state.get("protocol", []), key=lambda s: s["order"])
        for i, step in enumerate(protocol, start=1):
            step["step"] = i
        nearest = state.get("nearest") or {}
        agg = state.get("aggregation") or {}
        return VerificationResult(
            decision=VerificationDecision(state["decision"]),
            decided_by=state.get("decided_by", ""),
            reason=state.get("reason", ""),
            feedback=state.get("feedback", ""),
            score=agg.get("score"),
            max_similarity=nearest.get("similarity"),
            nearest_report_id=nearest.get("report_id"),
            fingerprint=state.get("fingerprint") or [],
            protocol=protocol,
            llm_calls=state.get("llm_calls", 0),
            duration_ms=int((time.perf_counter() - started) * 1000),
            verdicts=[v.to_dict() for v in sorted(state.get("verdicts", []), key=lambda v: v.judge)],
            vision_calls=state.get("vision_calls", 0),
            image_descriptions=state.get("image_descriptions") or [],
        )
