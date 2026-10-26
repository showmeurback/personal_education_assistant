"""Карта пробелов: какие темы курса студенту стоит подтянуть.

Гибридная схема, как и в проверке отчётов: решение принимает символьный компонент,
нейросетевой — объясняет.

Символьная часть (детерминированная, воспроизводимая):
  * свидетельства об освоении собираются из трёх источников: тесты (доля верных
    ответов), пробный экзамен (балл ответа 0–100), лабораторные работы (итог
    последнего отчёта);
  * свидетельства одной темы объединяются по совпадению лемм названия
    (коэффициент Жаккара ≥ 0,6);
  * уровень освоения темы M = Σ w_k·m_k / Σ w_k, где m_k ∈ [0, 1] — результат
    k-го свидетельства, w_k = 0,6^k — вес (k = 0 для самого свежего);
  * тема считается пробелом при M < 0,7; пробелы упорядочены по M, при равенстве —
    по числу свидетельств.

Нейросетевая часть: языковая модель по конкретным ошибкам (неверные вопросы
теста, недочёты ответов экзамена, невыполненные критерии отчёта) формулирует
короткий план повторения для каждой слабой темы; гибридный поиск находит
фрагменты лекций курса по теме. При недоступности модели карта строится без
советов — уровни и ранжирование от модели не зависят.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from log import logger

WEAK_THRESHOLD = 0.7
STRONG_THRESHOLD = 0.85
DECAY = 0.6
MERGE_JACCARD = 0.6
MAX_WEAK = 5

LAB_MASTERY = {"approved": 1.0, "pending": 0.8, "ai-rejected": 0.3, "not-approved": 0.3}


@dataclass
class Evidence:
    source: str          # test | exam | lab
    title: str           # тема теста, вопрос экзамена, название лабораторной
    mastery: float       # 0..1
    created_at: str
    details: list[str] = field(default_factory=list)  # конкретные ошибки и недочёты


@dataclass
class Topic:
    topic: str
    mastery: float
    level: str
    evidence: dict
    details: list[str]
    advice: str = ""
    sources: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _lemma_key(text: str) -> frozenset[str]:
    from agents.verification.normalizer import TextNormalizer
    try:
        return frozenset(TextNormalizer().lemmas(text))
    except Exception:  # без лемматизатора — по словам
        return frozenset(w for w in text.lower().split() if len(w) > 3)


def _jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else float(a == b)


def group_evidence(items: list[Evidence]) -> list[tuple[str, list[Evidence]]]:
    """Объединение свидетельств одной темы по леммам названия (символьно)."""
    groups: list[tuple[str, frozenset, list[Evidence]]] = []
    for ev in sorted(items, key=lambda e: e.created_at, reverse=True):
        key = _lemma_key(ev.title)
        for i, (name, gkey, evs) in enumerate(groups):
            if _jaccard(key, gkey) >= MERGE_JACCARD:
                evs.append(ev)
                break
        else:
            groups.append((ev.title, key, [ev]))
    return [(name, evs) for name, _k, evs in groups]


def mastery_of(evs: list[Evidence]) -> float:
    """M = Σ w_k·m_k / Σ w_k, w_k = DECAY^k по свежести (evs отсортированы от новых к старым)."""
    weights = [DECAY ** k for k in range(len(evs))]
    return round(sum(w * e.mastery for w, e in zip(weights, evs)) / sum(weights), 3)


def level_of(m: float) -> str:
    return "слабо" if m < 0.5 else "нужно подтянуть" if m < WEAK_THRESHOLD else \
        "средне" if m < STRONG_THRESHOLD else "хорошо"


def rank_topics(items: list[Evidence]) -> tuple[list[Topic], list[Topic]]:
    """(пробелы — от самого слабого, освоенные темы)."""
    topics = []
    for name, evs in group_evidence(items):
        m = mastery_of(evs)
        counts = {s: sum(1 for e in evs if e.source == s) for s in ("test", "exam", "lab")}
        details = [d for e in evs for d in e.details][:8]
        topics.append(Topic(name, m, level_of(m), counts, details))
    weak = sorted((t for t in topics if t.mastery < WEAK_THRESHOLD),
                  key=lambda t: (t.mastery, -sum(t.evidence.values())))[:MAX_WEAK]
    strong = sorted((t for t in topics if t.mastery >= STRONG_THRESHOLD), key=lambda t: -t.mastery)[:3]
    return weak, strong


# ── сбор свидетельств из базы знаний ─────────────────────────────────────────

def collect_evidence(student_id: int, course_id: int) -> list[Evidence]:
    from database.sql.repositories.exam_results import ExamResultRepository
    from database.sql.repositories.reports import ReportRepository
    from database.sql.repositories.test_results import TestResultRepository

    items: list[Evidence] = []
    tests = TestResultRepository()
    for rid, topic, source, _diff, _total, _ok, _wrong, pct, created in \
            tests.get_by_student_and_course(student_id, course_id):
        if not topic:
            continue
        wrong = [f"Тест: ошибка в вопросе «{q[1][:160]}» (выбран {q[3] or '—'}, верно {q[4]})"
                 for q in tests.get_answers(rid) if not q[5]][:3]
        items.append(Evidence("test", topic.replace("Файл: ", ""), float(pct or 0) / 100, created, wrong))

    exams = ExamResultRepository()
    for eid, _total, _avg, _completed, created in exams.get_by_student_and_course(student_id, course_id):
        for _qid, question, _ans, verdict, rec, issues, score in exams.get_answers(eid):
            if score is None:
                continue
            issues = issues if isinstance(issues, list) else json.loads(issues or "[]")
            det = [f"Экзамен: {i}" for i in issues[:3]] + ([f"Рекомендация: {rec}"] if rec and verdict != "correct" else [])
            items.append(Evidence("exam", question[:160], float(score) / 100, created, det))

    repo = ReportRepository()
    latest: dict[int, dict] = {}
    for r in repo.get_student_reports(student_id):
        if r["course_id"] == course_id and r["lab_id"] not in latest:
            latest[r["lab_id"]] = r  # отчёты отсортированы от новых к старым
    for r in latest.values():
        m = LAB_MASTERY.get(r["status"])
        if m is None:
            continue
        det = []
        if m < WEAK_THRESHOLD:
            check = repo.get_check(r["report_id"]) or {}
            for step in check.get("protocol") or []:
                for c in (step.get("details") or {}).get("criteria") or []:
                    if c.get("met") is False and c.get("comment"):
                        det.append(f"Отчёт: {c.get('name')}: {c['comment']}")
            if r.get("comment"):
                det.insert(0, f"Комментарий преподавателя: {r['comment']}")
        title = f"ЛР {r['lab_number']}. {r['lab_title']}"
        items.append(Evidence("lab", title, m, r["created_at"], det[:4]))
    return items


# ── нейросетевая часть: план повторения и фрагменты лекций ───────────────────

ADVICE_SYSTEM = """[TASK:WEAK_TOPICS]
Ты — наставник студента. По каждой слабой теме курса и конкретным ошибкам студента
напиши по-русски 2–3 предложения: что именно повторить и как проверить себя.
Опирайся только на перечисленные ошибки, не придумывай новых.
Ответь СТРОГО JSON-массивом: [{"topic": "название темы как в запросе", "advice": "совет"}]"""

_advice_cache: dict[str, dict[str, str]] = {}


def advise(weak: list[Topic], course_title: str = "") -> bool:
    if not weak:
        return False
    payload = "\n\n".join(f"Тема: {t.topic}\nУровень освоения: {t.mastery:.0%}\nОшибки:\n" +
                          ("\n".join(f"- {d}" for d in t.details) or "- подробностей нет")
                          for t in weak)
    key = hashlib.sha256((course_title + payload).encode()).hexdigest()
    if key not in _advice_cache:
        from langchain_core.messages import HumanMessage, SystemMessage

        from llm.chat import invoke_text, split_model
        from llm.json_utils import extract_json
        from settings import llm_settings
        try:
            name, thinking = split_model(llm_settings.feedback_model)
            raw = invoke_text([SystemMessage(content=ADVICE_SYSTEM),
                               HumanMessage(content=f"Курс: {course_title}\n\n{payload}")],
                              temperature=0.3, max_tokens=250 * len(weak) + 200, model=name, thinking=thinking)
        except Exception as exc:
            logger.warning(f"Советы по слабым темам не получены: {type(exc).__name__}: {exc}")
            return False
        data = extract_json(raw)
        advice = {}
        for item in data if isinstance(data, list) else []:
            if isinstance(item, dict) and item.get("topic") and item.get("advice"):
                advice[str(item["topic"]).strip()] = " ".join(str(item["advice"]).split())[:600]
        if len(_advice_cache) > 500:
            _advice_cache.clear()
        _advice_cache[key] = advice
    advice = _advice_cache[key]
    for i, t in enumerate(weak):
        t.advice = advice.get(t.topic) or (list(advice.values())[i] if len(advice) == len(weak) else "")
    return any(t.advice for t in weak)


def attach_sources(weak: list[Topic], course_id: int) -> None:
    """Фрагменты лекций курса по каждой теме (гибридный поиск BM25 + векторы)."""
    from database.sql import CourseRepository
    from database.vector.repositories import StorageManager
    try:
        storage_id = CourseRepository().get_storage_id(course_id)
        store = StorageManager.get_vector_storage(storage_id) if storage_id else None
    except Exception:
        store = None
    if store is None:
        return
    from concurrent.futures import ThreadPoolExecutor

    def search(topic: str):
        try:
            return store.hybrid_search(topic, k=3, alpha=0.6)
        except Exception as exc:
            logger.warning(f"Поиск фрагментов для темы «{topic}» не удался: {exc}")
            return []

    with ThreadPoolExecutor(max_workers=5) as pool:  # темы ищутся параллельно
        found = list(pool.map(search, [t.topic for t in weak]))
    for t, chunks in zip(weak, found):
        seen, t.sources = set(), []
        for c in chunks:
            snippet = " ".join(c.text.split())[:220]
            if snippet not in seen:  # одинаковые фрагменты (повторы в лекции) не дублируются
                seen.add(snippet)
                t.sources.append({"filename": c.filename, "snippet": snippet})


def weak_topics(student_id: int, course_id: int, course_title: str = "", with_advice: bool = True) -> dict:
    """with_advice=False — только символьная карта (мгновенно); советы и фрагменты лекций
    требуют обращения к модели и поиску, поэтому интерфейс запрашивает их вторым запросом."""
    items = collect_evidence(student_id, course_id)
    weak, strong = rank_topics(items)
    llm_used = False
    if with_advice:  # совет модели и поиск фрагментов лекций выполняются параллельно
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            advice_job = pool.submit(advise, weak, course_title)
            sources_job = pool.submit(attach_sources, weak, course_id)
            llm_used = advice_job.result()
            sources_job.result()
    return {
        "topics": [t.to_dict() for t in weak],
        "strong": [{"topic": t.topic, "mastery": t.mastery} for t in strong],
        "evidence_total": len(items),
        "llm_used": llm_used,
        "with_advice": with_advice,
        "method": (f"Уровень освоения M — взвешенное среднее результатов тестов, экзамена и отчётов "
                   f"(свежие весят больше, вес 0,6^k); пробел — M < {WEAK_THRESHOLD}. "
                   "Советы формирует языковая модель по вашим конкретным ошибкам."),
    }
