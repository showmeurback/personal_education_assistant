"""Пробный экзамен. Состояние экзамена хранится в памяти процесса
(идентификатор экзамена → сессия) и привязано к студенту."""
from __future__ import annotations

import threading
import time
from uuid import uuid4

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from agents.exam.exam_agent import ExamAgent
from auth import CurrentUser, ensure_course_access, require_student
from database.sql.repositories.exam_results import ExamResultRepository
from log import logger
from models.exam import ExamQuestion, ExamResult, ExamSession

from ..app import app

_agent = ExamAgent()
_store: dict[str, tuple[int, int, ExamSession, float]] = {}
_lock = threading.Lock()
_TTL = 4 * 3600


class StartExamRequest(BaseModel):
    question_count: int = Field(default=3, ge=1, le=10)
    language: str = Field(default="ru", min_length=2, max_length=8)


class SubmitAnswerRequest(BaseModel):
    exam_id: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=8000)


def _question(q: ExamQuestion | None) -> dict | None:
    # эталонный ответ клиенту не передаётся (раньше он отправлялся вместе с вопросом)
    return None if q is None else {"id": q.id, "text": q.text}


def _result(r: ExamResult) -> dict:
    return {
        "question_id": r.question.id, "question_text": r.question.text, "user_answer": r.user_answer,
        "verdict": r.verdict, "recommendation": r.recommendation, "issues": list(r.issues),
        "score": r.score, "summary": r.raw_feedback,
    }


def _get(course_id: int, exam_id: str, student_id: int) -> ExamSession:
    record = _store.get(exam_id)
    if record is None or record[0] != course_id or record[1] != student_id:
        raise HTTPException(404, "Экзамен не найден или истёк")
    return record[2]


@app.post("/api/v1/courses/{course_id}/exam/start", status_code=201, tags=["Экзамен"])
def start_exam(course_id: int, payload: StartExamRequest, user: CurrentUser = Depends(require_student)):
    ensure_course_access(user, course_id)
    try:
        session = _agent.create_session(course_id=course_id, question_count=payload.question_count,
                                        language=payload.language)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    first = session.next_question()
    exam_id = uuid4().hex
    now = time.time()
    with _lock:
        for key in [k for k, v in _store.items() if now - v[3] > _TTL]:
            del _store[key]
        _store[exam_id] = (course_id, user.id, session, now)
    return {"exam_id": exam_id, "question": _question(first), "total_questions": session.total,
            "has_more_questions": session.has_next_question()}


@app.post("/api/v1/courses/{course_id}/exam/answer", tags=["Экзамен"])
def submit_answer(course_id: int, payload: SubmitAnswerRequest, user: CurrentUser = Depends(require_student)):
    session = _get(course_id, payload.exam_id, user.id)
    try:
        result = session.submit_answer(payload.answer.strip())
    except ValueError:
        raise HTTPException(409, "Нет активного вопроса")
    next_q = session.next_question() if session.has_next_question() else None
    completed = next_q is None
    if completed:
        _save(user.id, course_id, session)
    return {"evaluation": _result(result), "next_question": _question(next_q),
            "has_more_questions": session.has_next_question(), "completed": completed}


@app.get("/api/v1/courses/{course_id}/exam/summary", tags=["Экзамен"])
def exam_summary(course_id: int, exam_id: str, user: CurrentUser = Depends(require_student)):
    session = _get(course_id, exam_id, user.id)
    scores = [float(r.score) for r in session.results if r.score is not None]
    return {
        "exam_id": exam_id, "course_id": course_id,
        "completed": not session.has_next_question() and session.active_question is None,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "results": [_result(r) for r in session.results],
    }


def _save(student_id: int, course_id: int, session: ExamSession) -> None:
    if session.saved:
        return
    scores = [float(r.score) for r in session.results if r.score is not None]
    try:
        ExamResultRepository().save(
            student_id=student_id, course_id=course_id, total_questions=len(session.results),
            avg_score=(sum(scores) / len(scores)) if scores else None, completed=True,
            answers=[{
                "question_id": r.question.id, "question_text": r.question.text,
                "user_answer": r.user_answer, "verdict": r.verdict,
                "recommendation": r.recommendation, "issues": list(r.issues), "score": r.score,
            } for r in session.results],
        )
        session.saved = True
    except Exception as exc:
        logger.error(f"Не удалось сохранить результат экзамена: {exc}")
