import jwt
import pytest

from auth.security import create_token, decode_token, hash_password, needs_rehash, verify_password


def test_password_hashing_roundtrip():
    h = hash_password("secret")
    assert h != "secret" and verify_password("secret", h) and not verify_password("wrong", h)
    assert not needs_rehash(h)


def test_legacy_plaintext_password_supported_and_flagged():
    assert verify_password("student1", "student1") and needs_rehash("student1")


def test_token_roundtrip_and_tamper():
    token = create_token(5, "student", "Иван Петров")
    payload = decode_token(token)
    assert payload["sub"] == "5" and payload["role"] == "student"
    with pytest.raises(jwt.PyJWTError):
        decode_token(token[:-2] + ("aa" if not token.endswith("aa") else "bb"))


def test_exam_verdict_is_aligned_with_score(monkeypatch):
    from agents.exam import exam_agent
    from models.exam import ExamQuestion
    monkeypatch.setattr(exam_agent, "invoke_text",
                        lambda *a, **k: '{"verdict": "correct", "score": 40, "issues": [], "recommendation": "r"}')
    res = exam_agent.ExamAgent().evaluate_answer(question=ExamQuestion(1, "Q?"), answer="ответ",
                                                 context="", language="ru")
    assert res.verdict == "partial" and res.score == "40"
