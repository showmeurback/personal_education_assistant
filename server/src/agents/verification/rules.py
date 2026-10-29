"""Продукционные правила формальной проверки отчёта (символьный компонент).

Каждое правило имеет вид «ЕСЛИ <условие на признаках отчёта> ТО <вывод>».
Факты (признаки) извлекаются детерминированно: число слов, доля кириллицы,
наличие обязательных разделов, доля ключевых понятий задания в отчёте.
Вывод правила: PASS — условие выполнено; WARN — замечание, не блокирующее
проверку; BLOCK — отчёт отклоняется без обращения к языковой модели.
Правила и их параметры берутся из описания лабораторной работы
(база знаний курса), поэтому преподаватель меняет их без изменения кода.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Callable

from settings import verification_settings as cfg


class Outcome(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class LabRequirements:
    task: str
    min_words: int | None = None
    required_sections: list[str] = field(default_factory=list)
    # задания других лабораторных работ того же курса (для правила R7)
    other_tasks: list[str] = field(default_factory=list)

    @classmethod
    def from_db(cls, task: str | None, min_words: int | None, required_sections: str | None):
        sections = [s.strip() for s in re.split(r"[\n;,]+", required_sections or "") if s.strip()]
        return cls(task=task or "", min_words=min_words, required_sections=sections)


@dataclass
class ReportFacts:
    """Факты об отчёте, извлекаемые до применения правил."""
    word_count: int
    char_count: int
    cyrillic_share: float
    lemmas: list[str]
    lemma_set: set[str]
    task_terms: list[str]
    task_coverage: float
    text_lower: str


@dataclass
class RuleResult:
    rule_id: str
    title: str
    outcome: Outcome
    message: str
    value: float | int | None = None
    threshold: float | int | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["outcome"] = self.outcome.value
        return d


@dataclass
class Rule:
    rule_id: str
    title: str
    check: Callable[[ReportFacts, LabRequirements], RuleResult]


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
_LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")
_CYR_RE = re.compile(r"[А-Яа-яЁё]")

# ниже этой доли покрытия понятий задания отчёт считается «вероятно не по теме»
TASK_COVERAGE_WARN = 0.20


def extract_task_terms(task_lemmas: list[str], max_terms: int = 25) -> list[str]:
    """Ключевые понятия задания: леммы длиной ≥ 4 символов в порядке частоты."""
    counts: dict[str, int] = {}
    for lemma in task_lemmas:
        if len(lemma) >= 4 and not lemma.isdigit():
            counts[lemma] = counts.get(lemma, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [t for t, _ in ordered[:max_terms]]


def build_facts(text: str, lemmas: list[str], task_lemmas: list[str]) -> ReportFacts:
    words = _WORD_RE.findall(text)
    letters = _LETTER_RE.findall(text)
    cyr = _CYR_RE.findall(text)
    lemma_set = set(lemmas)
    terms = extract_task_terms(task_lemmas)
    coverage = (sum(1 for t in terms if t in lemma_set) / len(terms)) if terms else 1.0
    return ReportFacts(
        word_count=len(words),
        char_count=len(text),
        cyrillic_share=(len(cyr) / len(letters)) if letters else 0.0,
        lemmas=lemmas,
        lemma_set=lemma_set,
        task_terms=terms,
        task_coverage=coverage,
        text_lower=text.lower(),
    )


_HEADING_PREFIX = re.compile(r"^[\s#*\-–—•\d.)]*")


def _has_heading(text_lower: str, section: str) -> bool:
    """Раздел считается присутствующим, если какая-либо строка отчёта начинается с его
    названия (с учётом нумерации и маркеров), — упоминание слова внутри абзаца не считается."""
    # основа для множественного числа: «Цель» → «Цели», «Задача» → «Задачи»
    stems = [section] + ([section[:-1]] if len(section) > 3 and section[-1] in "ьйая" else [])
    for line in text_lower.splitlines():
        head = _HEADING_PREFIX.sub("", line, count=1)
        for stem in stems:
            if not head.startswith(stem):
                continue
            rest = head[len(stem):]
            # «Вывод», «Выводы», «Вывод:», «Цели» — да; «выводится …», «целый» — нет
            if rest[:1] and rest[0] in "ыиьяа":
                rest = rest[1:]
            if not rest or not rest[0].isalpha():
                return True
    return False


# ── Правила ────────────────────────────────────────────────────────────────────

def _r_non_empty(f: ReportFacts, req: LabRequirements) -> RuleResult:
    ok = f.word_count >= 20
    return RuleResult("R1", "Отчёт содержит текст", Outcome.PASS if ok else Outcome.BLOCK,
                      "Текст отчёта извлечён" if ok else "Отчёт пуст или текст не удалось извлечь",
                      f.word_count, 20)


def _r_min_words(f: ReportFacts, req: LabRequirements) -> RuleResult:
    limit = req.min_words if req.min_words is not None else cfg.default_min_words
    ok = f.word_count >= limit
    return RuleResult("R2", "Минимальный объём", Outcome.PASS if ok else Outcome.BLOCK,
                      f"Объём {f.word_count} слов" + ("" if ok else f" меньше требуемых {limit}"),
                      f.word_count, limit)


def _alternatives(section: str) -> list[str]:
    """«Вывод|Заключение» — раздел засчитывается при наличии любого из названий."""
    return [a.strip().lower() for a in re.split(r"[|/]", section) if a.strip()]


def _section_label(section: str) -> str:
    return " или ".join(f"«{a.strip()}»" for a in re.split(r"[|/]", section) if a.strip())


def _r_sections(f: ReportFacts, req: LabRequirements) -> RuleResult:
    if not req.required_sections:
        return RuleResult("R3", "Обязательные разделы", Outcome.PASS, "Разделы не заданы преподавателем")
    missing = [s for s in req.required_sections
               if not any(_has_heading(f.text_lower, alt) for alt in _alternatives(s))]
    ok = not missing
    return RuleResult("R3", "Обязательные разделы", Outcome.PASS if ok else Outcome.BLOCK,
                      "Все обязательные разделы присутствуют" if ok
                      else "Отсутствуют разделы: " + ", ".join(_section_label(m) for m in missing),
                      len(req.required_sections) - len(missing), len(req.required_sections))


def _r_language(f: ReportFacts, req: LabRequirements) -> RuleResult:
    ok = f.cyrillic_share >= 0.5
    return RuleResult("R4", "Язык отчёта", Outcome.PASS if ok else Outcome.WARN,
                      "Отчёт на русском языке" if ok
                      else f"Доля кириллицы {f.cyrillic_share:.0%} — отчёт, вероятно, не на русском языке",
                      round(f.cyrillic_share, 3), 0.5)


def _r_length_limit(f: ReportFacts, req: LabRequirements) -> RuleResult:
    ok = f.char_count <= cfg.max_report_chars
    return RuleResult("R5", "Предельный объём", Outcome.PASS if ok else Outcome.WARN,
                      "Объём в допустимых пределах" if ok
                      else f"Отчёт длиннее {cfg.max_report_chars} символов: искусственному интеллекту передаётся начало текста",
                      f.char_count, cfg.max_report_chars)


def _r_task_coverage(f: ReportFacts, req: LabRequirements) -> RuleResult:
    if not f.task_terms:
        return RuleResult("R6", "Соответствие теме (по понятиям задания)", Outcome.PASS,
                          "Задание не содержит ключевых понятий")
    ok = f.task_coverage >= TASK_COVERAGE_WARN
    found = [t for t in f.task_terms if t in f.lemma_set]
    return RuleResult("R6", "Соответствие теме (по понятиям задания)",
                      Outcome.PASS if ok else Outcome.WARN,
                      f"Найдено {len(found)} из {len(f.task_terms)} ключевых понятий задания"
                      + ("" if ok else " — отчёт, вероятно, не по теме"),
                      round(f.task_coverage, 3), TASK_COVERAGE_WARN)


RULES: list[Rule] = [
    Rule("R1", "Отчёт содержит текст", _r_non_empty),
    Rule("R2", "Минимальный объём", _r_min_words),
    Rule("R3", "Обязательные разделы", _r_sections),
    Rule("R4", "Язык отчёта", _r_language),
    Rule("R5", "Предельный объём", _r_length_limit),
    Rule("R6", "Соответствие теме", _r_task_coverage),
]


def apply_rules(facts: ReportFacts, req: LabRequirements) -> list[RuleResult]:
    results = [rule.check(facts, req) for rule in RULES]
    # R2 не имеет смысла, если R1 уже заблокировал отчёт
    if results[0].outcome is Outcome.BLOCK:
        results = [results[0]]
    return results
