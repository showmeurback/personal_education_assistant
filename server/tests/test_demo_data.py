"""Согласованность демонстрационных данных (без базы данных)."""
import random

from demo import data as D
from demo.materials import EXAMS, LECTURES
from demo.questions import QUESTIONS
from demo.seed import LAB_MIN_WORDS, _report_text


def test_every_test_topic_has_questions():
    for _s, course, tests in D.test_plan:
        for topic, _difficulty, total, correct in tests:
            bank = QUESTIONS[course][topic]
            assert len(bank) >= total and 0 <= correct <= total
            for question, options, answer in bank:
                assert len(options) == 4 and answer in "ABCD" and len(set(options)) == 4, question


def test_every_course_has_lecture_exam_and_labs():
    for i in range(1, len(D.courses_raw) + 1):
        key = f"c{i}"
        assert len(LECTURES[key]) > 1000 and EXAMS[key] and D.labs_data[key]


def test_references_are_valid():
    students = {f"s{i}" for i in range(1, len(D.students_data) + 1)}
    courses = {f"c{i}" for i in range(1, len(D.courses_raw) + 1)}
    assert {s for s, _ in D.enrollments} <= students and {c for _, c in D.enrollments} <= courses
    for s, c, lab_idx, status, _comment in D.reports_raw:
        assert s in students and lab_idx < len(D.labs_data[c])
        assert status in {"approved", "pending", "not-approved"}
        assert (s, c) in D.enrollments


def test_report_text_passes_formal_rules():
    """Отчёты демонстрационных студентов проходят правила R2 и R3 своей лабораторной."""
    from agents.verification.rules import LabRequirements, Outcome, apply_rules, build_facts
    from agents.verification.normalizer import TextNormalizer
    rng, norm = random.Random(1), TextNormalizer()
    for course, labs in D.labs_data.items():
        for number, title, task in labs:
            text = _report_text(number, title, task, "Иван", "Петров", rng)
            req = LabRequirements(task=task, min_words=LAB_MIN_WORDS, required_sections=["Цель", "Вывод"])
            facts = build_facts(text, norm.lemmas(text), norm.lemmas(task))
            blocked = [r for r in apply_rules(facts, req) if r.outcome == Outcome.BLOCK]
            assert not blocked, (course, number, [r.message for r in blocked])
