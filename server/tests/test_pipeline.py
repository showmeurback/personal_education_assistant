"""Интеграционные тесты гибридного конвейера (заглушка LLM, индекс отпечатков в памяти)."""
import pytest

from agents.verification import judges as judges_module
from agents.verification.judges import JudgeVerdict
from agents.verification.pipeline import VerificationPipeline
from agents.verification.rules import LabRequirements
from database.vector.repositories.report_index import InMemoryReportIndex
from models.enums import VerificationDecision as D
from fixtures import GOOD_REPORT, OFF_TOPIC_REPORT, PARAPHRASED_REPORT, TASK

REQ = LabRequirements(task=TASK, min_words=60, required_sections=["Цель", "Вывод"])


async def check(pipeline, text, student=1, lab=1, req=REQ):
    return await pipeline.run(text=text, requirements=req, student_id=student, lab_id=lab)


async def test_typical_good_report_is_approved_with_full_protocol():
    r = await check(VerificationPipeline(InMemoryReportIndex()), GOOD_REPORT)
    assert r.decision is D.APPROVE and r.decided_by == "judges" and r.llm_calls == 3
    kinds = [s["kind"] for s in r.protocol]
    assert kinds == ["symbolic", "symbolic", "symbolic", "symbolic", "neural", "neural", "neural", "symbolic"]
    assert r.protocol[3]["title"].startswith("Соответствие лабораторной работе")


async def test_copy_of_other_students_report_is_rejected_without_llm():
    index = InMemoryReportIndex()
    p = VerificationPipeline(index)
    first = await check(p, GOOD_REPORT, student=1)
    index.add(first.fingerprint, report_id=1, student_id=1, lab_id=1)
    copy = await check(p, GOOD_REPORT, student=2)
    assert copy.decision is D.REJECT and copy.decided_by == "simhash" and copy.llm_calls == 0
    assert copy.nearest_report_id == 1


async def test_own_resubmission_is_not_plagiarism():
    index = InMemoryReportIndex()
    p = VerificationPipeline(index)
    first = await check(p, GOOD_REPORT, student=1)
    index.add(first.fingerprint, report_id=1, student_id=1, lab_id=1)
    again = await check(p, GOOD_REPORT, student=1)
    assert again.decided_by != "simhash"


async def test_same_text_in_other_lab_is_not_compared():
    index = InMemoryReportIndex()
    p = VerificationPipeline(index)
    first = await check(p, GOOD_REPORT, student=1, lab=1)
    index.add(first.fingerprint, report_id=1, student_id=1, lab_id=1)
    other_lab = await check(p, GOOD_REPORT, student=2, lab=2)
    assert other_lab.decided_by != "simhash"


async def test_paraphrase_passes_filter_and_reaches_judges():
    index = InMemoryReportIndex()
    p = VerificationPipeline(index)
    first = await check(p, GOOD_REPORT, student=1)
    index.add(first.fingerprint, report_id=1, student_id=1, lab_id=1)
    para = await check(p, PARAPHRASED_REPORT, student=2)
    assert para.decided_by == "judges" and para.llm_calls >= 3


@pytest.mark.parametrize("text", ["", "Отчёт сдан.", "Цель. " * 30])
async def test_formally_invalid_reports_rejected_by_rules(text):
    r = await check(VerificationPipeline(InMemoryReportIndex()), text)
    assert r.decision is D.REJECT and r.decided_by == "rules" and r.llm_calls == 0
    assert "формальные требования" in r.feedback


async def test_off_topic_report_never_auto_approved():
    r = await check(VerificationPipeline(InMemoryReportIndex()), OFF_TOPIC_REPORT)
    assert r.decision in (D.REJECT, D.MANUAL_REVIEW)


async def test_llm_failure_degrades_to_manual_review(monkeypatch):
    async def broken(judge, requirements, report):
        return JudgeVerdict(judge, judge, valid=False, error="TimeoutError")
    monkeypatch.setattr("agents.verification.pipeline.run_judge", broken)
    r = await check(VerificationPipeline(InMemoryReportIndex()), GOOD_REPORT)
    assert r.decision is D.MANUAL_REVIEW and "валидных оценок" in r.reason


async def test_judge_disagreement_goes_to_teacher(monkeypatch):
    async def split(judge, requirements, report):
        return JudgeVerdict(judge, judge, valid=True, verdict=(judge != "strict"), confidence=0.9)
    monkeypatch.setattr("agents.verification.pipeline.run_judge", split)
    r = await check(VerificationPipeline(InMemoryReportIndex()), GOOD_REPORT)
    assert r.decision is D.MANUAL_REVIEW and r.score is not None


async def test_unanimous_reject_produces_feedback(monkeypatch):
    async def reject(judge, requirements, report):
        return JudgeVerdict(judge, judge, valid=True, verdict=False, confidence=0.9, summary="Не раскрыта тема")
    monkeypatch.setattr("agents.verification.pipeline.run_judge", reject)
    r = await check(VerificationPipeline(InMemoryReportIndex()), GOOD_REPORT)
    assert r.decision is D.REJECT and r.feedback and r.llm_calls == 4


async def test_symbolic_and_neural_modes():
    sym = VerificationPipeline(InMemoryReportIndex(), mode="symbolic")
    r = await check(sym, GOOD_REPORT)
    assert r.decision is D.APPROVE and r.llm_calls == 0
    r = await check(sym, OFF_TOPIC_REPORT)
    assert r.decision is D.REJECT
    neu = VerificationPipeline(InMemoryReportIndex(), mode="neural")
    r = await check(neu, "")
    assert r.llm_calls == 3 and not any(s["kind"] == "symbolic" and s["title"].startswith("Продукционные") for s in r.protocol)


async def test_reproducible_symbolic_part():
    p = VerificationPipeline(InMemoryReportIndex())
    a = await check(p, GOOD_REPORT)
    b = await check(p, GOOD_REPORT)
    assert a.fingerprint == b.fingerprint
    assert a.protocol[1]["details"] == b.protocol[1]["details"]
