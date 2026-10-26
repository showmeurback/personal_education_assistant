"""Нейросетевой компонент: ансамбль из трёх LLM-оценщиков с разными позициями."""
from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from llm.chat import ainvoke_text, split_model
from llm.json_utils import extract_json
from settings import llm_settings, verification_settings as cfg
from .prompts import JUDGE_SYSTEM, JUDGE_USER, STANCES

REPORT_CHARS_FOR_LLM = cfg.max_report_chars

# Кэш оценок для сравнительного эксперимента: в нейросетевом и гибридном вариантах
# оценщики получают идентичные входы (нулевая температура), поэтому оценка вычисляется
# один раз. В рабочем режиме кэш выключен.
_cache: dict[tuple[str, str, str, str], "JudgeVerdict"] | None = None


_replay_delay = True


def enable_cache(replay_delay: bool = True) -> None:
    """replay_delay=False — повторное использование оценки без воспроизведения времени ответа."""
    global _cache, _replay_delay
    _cache = {}
    _replay_delay = replay_delay


def disable_cache() -> None:
    global _cache
    _cache = None


@dataclass
class JudgeVerdict:
    judge: str
    title: str
    valid: bool
    model: str = ""
    verdict: bool | None = None
    confidence: float | None = None
    summary: str = ""
    criteria: list[dict] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0

    @property
    def p_accept(self) -> float | None:
        """Вероятность «отчёт соответствует», выраженная оценщиком."""
        if not self.valid or self.verdict is None or self.confidence is None:
            return None
        return self.confidence if self.verdict else 1.0 - self.confidence

    def to_dict(self) -> dict:
        d = asdict(self)
        d["p_accept"] = self.p_accept
        return d


def parse_judge_output(judge: str, raw: str) -> JudgeVerdict:
    title = STANCES[judge]["title"]
    data = extract_json(raw)
    if not isinstance(data, dict) or "verdict" not in data:
        return JudgeVerdict(judge, title, valid=False, error="Ответ модели не содержит JSON с полем verdict")
    verdict = data.get("verdict")
    if isinstance(verdict, str):
        verdict = verdict.strip().lower() in {"true", "да", "yes", "1", "соответствует"}
    if not isinstance(verdict, bool):
        return JudgeVerdict(judge, title, valid=False, error="Некорректное значение verdict")
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    if confidence > 1.0:  # модель ответила в процентах
        confidence = confidence / 100.0
    confidence = min(1.0, max(0.0, confidence))
    criteria = [c for c in (data.get("criteria") or []) if isinstance(c, dict)][:8]
    return JudgeVerdict(judge, title, valid=True, verdict=verdict, confidence=round(confidence, 3),
                        summary=str(data.get("summary", ""))[:500], criteria=criteria)


async def run_judge(judge: str, requirements: str, report_text: str) -> JudgeVerdict:
    model = llm_settings.model_for_judge(judge)
    key = (judge, model, requirements, report_text)
    if _cache is not None and key in _cache and _cache[key].valid:
        cached = _cache[key]
        # время ответа воспроизводится, чтобы замер длительности проверки оставался честным
        if _replay_delay:
            await asyncio.sleep(cached.duration_ms / 1000)
        return JudgeVerdict(**{k: v for k, v in cached.__dict__.items()})
    result = await _run_judge(judge, requirements, report_text, model)
    if _cache is not None:
        _cache[key] = result
    return result


async def _run_judge(judge: str, requirements: str, report_text: str, model: str) -> JudgeVerdict:
    stance = STANCES[judge]
    messages = [
        SystemMessage(content=JUDGE_SYSTEM.format(
            stance_marker=stance["marker"], role=stance["role"], stance=stance["stance"])),
        HumanMessage(content=JUDGE_USER.format(
            requirements=requirements.strip() or "(требования не указаны)",
            report=report_text[:REPORT_CHARS_FOR_LLM])),
    ]
    started = time.perf_counter()
    try:
        # temperature=0 — максимально воспроизводимые оценки
        # «модель@nothink» — гибридная модель без этапа рассуждения (быстрее)
        name, thinking = split_model(model)
        raw = await ainvoke_text(messages, temperature=0.0, max_tokens=llm_settings.judge_max_tokens,
                                 model=name, thinking=thinking)
        result = parse_judge_output(judge, raw)
        if not result.valid:
            result.error = f"{result.error}; начало ответа: {raw[:160]!r}"
    except Exception as exc:  # сетевые ошибки, лимиты API и т. п.
        result = JudgeVerdict(judge, stance["title"], valid=False, error=f"{type(exc).__name__}: {exc}"[:300])
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    result.model = model
    return result
