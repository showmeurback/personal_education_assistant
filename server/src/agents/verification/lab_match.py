"""Правило R7: соответствие отчёта своей лабораторной работе по векторным представлениям.

Лексическое правило R6 (доля понятий задания в отчёте) на реальных отчётах почти не
срабатывает: работы одной дисциплины используют общую терминологию. Самая частая
реальная ошибка — приложен отчёт по другой работе — обнаруживается сравнением:
к какой из лабораторных работ курса отчёт ближе по смыслу.

  s_target = cos(отчёт, задание этой работы)
  s_other  = max cos(отчёт, задание другой работы курса)

Сомнение (WARN) выставляется, если
  s_target < LAB_MATCH_MIN_SIM            — отчёт далёк от задания вообще, или
  s_other − s_target ≥ LAB_MATCH_MARGIN   — другое задание курса подходит лучше.

Векторы вычисляет модель эмбеддингов (нейросетевой компонент), а решение принимает
явное правило с порогами (символьный компонент). Пороги выбраны на наборе настройки
(10 реальных отчётов): сходство отчёта со своим заданием 0,57–0,90, с заданиями других
работ той же дисциплины 0,29–0,57 (своё задание всегда ближе на 0,20 и более), других
дисциплин 0,16–0,40. Сомнение не отклоняет отчёт само: арбитр не принимает такой отчёт
автоматически и передаёт его преподавателю (правило A5).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from settings import verification_settings as cfg

REPORT_CHARS = 6000  # начало отчёта (без титульного листа): цель, задание, ход работы


@dataclass
class LabMatch:
    checked: bool
    doubt: bool = False
    target_similarity: float | None = None
    best_other_similarity: float | None = None
    best_other_index: int | None = None
    reason: str = ""
    others: int = 0
    thresholds: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _cos(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


@lru_cache(maxsize=512)
def _task_vector(task: str) -> tuple[float, ...]:
    from llm.embeddings import _embed

    return tuple(_embed([task], input_type="query", timeout=cfg.lab_match_timeout, attempts=1)[0])


_report_cache: dict[str, list[float]] = {}


def _report_vector(text: str) -> list[float]:
    from llm.embeddings import embed_documents

    key = hashlib.sha256(text.encode()).hexdigest()
    if key not in _report_cache:
        if len(_report_cache) > 1000:
            _report_cache.clear()
        _report_cache[key] = embed_documents([text], timeout=cfg.lab_match_timeout, attempts=1)[0]
    return _report_cache[key]


def _embeddings_meaningful() -> bool:
    from settings import embedding_settings
    return embedding_settings.provider.lower() != "hash"


def match_lab(report_text: str, task: str, other_tasks: list[str]) -> LabMatch:
    """Синхронный вызов (сеть): вызывающая сторона выполняет его в отдельном потоке."""
    thresholds = {"min_similarity": cfg.lab_match_min_sim, "margin": cfg.lab_match_margin}
    if not cfg.lab_match_enabled or not task.strip():
        return LabMatch(False, reason="Проверка выключена или задание не указано", thresholds=thresholds)
    if not _embeddings_meaningful():  # хеш-векторы тестов не отражают смысл
        return LabMatch(False, reason="Векторы смысла недоступны (тестовые хеш-эмбеддинги)",
                        thresholds=thresholds)
    others = [t for t in other_tasks if t and t.strip() and t.strip() != task.strip()]
    try:
        rv = _report_vector(report_text[:REPORT_CHARS])
        s_target = _cos(rv, list(_task_vector(task)))
        sims = [_cos(rv, list(_task_vector(t))) for t in others]
    except Exception as exc:  # недоступность модели эмбеддингов не должна мешать проверке
        return LabMatch(False, reason=f"Модель эмбеддингов недоступна ({type(exc).__name__}); правило пропущено",
                        thresholds=thresholds)
    best = max(range(len(sims)), key=sims.__getitem__) if sims else None
    s_other = sims[best] if best is not None else None
    res = LabMatch(True, target_similarity=round(s_target, 3),
                   best_other_similarity=None if s_other is None else round(s_other, 3),
                   best_other_index=best, others=len(others), thresholds=thresholds)
    if s_other is not None and s_other - s_target >= cfg.lab_match_margin:
        res.doubt = True
        res.reason = (f"Отчёт ближе к заданию другой лабораторной работы курса ({s_other:.2f} против "
                      f"{s_target:.2f})")
    elif s_target < cfg.lab_match_min_sim:
        res.doubt = True
        res.reason = (f"Сходство отчёта с заданием {s_target:.2f} ниже порога {cfg.lab_match_min_sim}: "
                      "возможно, приложен отчёт не по этой работе")
    else:
        res.reason = (f"Сходство с заданием {s_target:.2f}"
                      + (f", с ближайшей другой работой курса {s_other:.2f}" if s_other is not None else ""))
    return res
