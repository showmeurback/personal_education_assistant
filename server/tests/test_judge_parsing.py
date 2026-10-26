from agents.verification.judges import parse_judge_output
from llm.json_utils import extract_json


def test_plain_json():
    r = parse_judge_output("strict", '{"verdict": true, "confidence": 0.8, "summary": "ok"}')
    assert r.valid and r.verdict is True and r.confidence == 0.8 and r.p_accept == 0.8


def test_fenced_json_with_reasoning():
    raw = '<think>рассуждаю…</think>Вот ответ:\n```json\n{"verdict": false, "confidence": 0.7}\n```'
    r = parse_judge_output("loyal", raw)
    assert r.valid and r.verdict is False and abs(r.p_accept - 0.3) < 1e-9


def test_string_verdict_and_percent_confidence():
    r = parse_judge_output("objective", '{"verdict": "да", "confidence": 85}')
    assert r.valid and r.verdict is True and r.confidence == 0.85


def test_missing_confidence_defaults_to_half():
    r = parse_judge_output("strict", '{"verdict": true}')
    assert r.confidence == 0.5


def test_garbage_is_invalid():
    r = parse_judge_output("strict", "Отчёт хороший, принимаю.")
    assert not r.valid and r.p_accept is None


def test_extract_json_finds_embedded_object():
    assert extract_json('Ответ: {"a": {"b": [1, 2]}} конец') == {"a": {"b": [1, 2]}}
    assert extract_json("нет json") is None


def test_each_judge_can_use_its_own_model():
    from settings import LLMSettings
    s = LLMSettings(LLM_PROVIDER="nvidia", LLM_JUDGE_MODELS="strict=m-a, objective=m-b")
    assert s.model_for_judge("strict") == "m-a" and s.model_for_judge("objective") == "m-b"
    assert s.model_for_judge("loyal") == s.model  # не указана — основная модель
    same = LLMSettings(LLM_PROVIDER="nvidia", LLM_JUDGE_MODELS="same")
    assert {same.model_for_judge(j) for j in ("strict", "objective", "loyal")} == {same.model}
