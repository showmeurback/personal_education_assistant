import json

from fastapi import Depends, HTTPException

from auth import CurrentUser, ensure_course_owner, get_current_user, require_student, require_teacher
from database.sql.repositories.exam_results import ExamResultRepository
from database.sql.repositories.reports import ReportRepository
from database.sql.repositories.test_results import TestResultRepository

from ..app import app


def _test_row(r, with_course: bool) -> dict:
    if with_course:
        keys = ["id", "course_id", "topic", "source", "difficulty", "total_questions",
                "correct_answers", "wrong_answers", "percentage", "created_at"]
    else:
        keys = ["id", "topic", "source", "difficulty", "total_questions", "correct_answers",
                "wrong_answers", "percentage", "created_at"]
    return dict(zip(keys, r))


@app.get("/api/v1/me/test-results", tags=["Профиль"])
def my_test_results(course_id: int | None = None, user: CurrentUser = Depends(require_student)):
    repo = TestResultRepository()
    if course_id is None:
        return {"results": [_test_row(r, True) for r in repo.get_by_student(user.id)]}
    return {"results": [{**_test_row(r, False), "course_id": course_id}
                        for r in repo.get_by_student_and_course(user.id, course_id)]}


@app.get("/api/v1/me/exam-results", tags=["Профиль"])
def my_exam_results(course_id: int | None = None, user: CurrentUser = Depends(require_student)):
    repo = ExamResultRepository()
    if course_id is None:
        keys = ["id", "course_id", "total_questions", "avg_score", "completed", "created_at"]
        return {"results": [dict(zip(keys, r)) for r in repo.get_by_student(user.id)]}
    keys = ["id", "total_questions", "avg_score", "completed", "created_at"]
    return {"results": [{**dict(zip(keys, r)), "course_id": course_id}
                        for r in repo.get_by_student_and_course(user.id, course_id)]}


def _check_result_access(owner: tuple[int, int] | None, user: CurrentUser) -> None:
    if owner is None:
        raise HTTPException(404, "Результат не найден")
    student_id, course_id = owner
    if user.is_student and student_id == user.id:
        return
    if user.is_teacher:
        ensure_course_owner(user, course_id)
        return
    raise HTTPException(403, "Нет доступа")


@app.get("/api/v1/test-results/{result_id}/answers", tags=["Профиль"])
def test_result_answers(result_id: int, user: CurrentUser = Depends(get_current_user)):
    repo = TestResultRepository()
    _check_result_access(repo.get_owner(result_id), user)
    return {"answers": [
        {"question_num": r[0], "question_text": r[1],
         "options": r[2] if isinstance(r[2], dict) else json.loads(r[2]),
         "user_answer": r[3], "correct_answer": r[4], "is_correct": r[5], "explanation": r[6]}
        for r in repo.get_answers(result_id)
    ]}


@app.get("/api/v1/exam-results/{result_id}/answers", tags=["Профиль"])
def exam_result_answers(result_id: int, user: CurrentUser = Depends(get_current_user)):
    repo = ExamResultRepository()
    _check_result_access(repo.get_owner(result_id), user)
    return {"answers": [
        {"question_id": r[0], "question_text": r[1], "user_answer": r[2], "verdict": r[3],
         "recommendation": r[4], "issues": json.loads(r[5]) if isinstance(r[5], str) else r[5],
         "score": r[6]}
        for r in repo.get_answers(result_id)
    ]}


@app.get("/api/v1/courses/{course_id}/analytics", tags=["Преподаватель"])
def course_analytics(course_id: int, user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    t, e, r = TestResultRepository(), ExamResultRepository(), ReportRepository()
    return {
        "test_averages": [
            {"student_id": a, "first_name": b, "last_name": c, "test_count": d,
             "avg_percentage": float(x) if x is not None else None}
            for (a, b, c, d, x) in t.get_course_analytics(course_id)],
        "exam_averages": [
            {"student_id": a, "first_name": b, "last_name": c, "exam_count": d,
             "avg_score": float(x) if x is not None else None}
            for (a, b, c, d, x) in e.get_course_analytics(course_id)],
        "report_statuses": [
            {"student_id": a, "first_name": b, "last_name": c, "lab_title": d, "status": s}
            for (a, b, c, d, s) in r.get_course_report_analytics(course_id)],
        "test_timeline": [
            {"student_id": a, "first_name": b, "last_name": c,
             "percentage": float(p) if p is not None else None, "topic": tp, "created_at": ts}
            for (a, b, c, p, tp, ts) in t.get_course_timeline(course_id)],
        "topic_accuracy": [
            {"topic": a, "total_q": b, "correct_q": c, "accuracy_pct": float(d or 0), "test_count": n}
            for (a, b, c, d, n) in t.get_topic_accuracy(course_id)],
        "hard_questions": [
            {"question_text": a, "attempts": b, "correct": c, "success_rate": float(d or 0), "topic": tp}
            for (a, b, c, d, tp) in t.get_hard_questions(course_id)],
        "difficulty_breakdown": [
            {"difficulty": a, "test_count": b, "avg_pct": float(c or 0)}
            for (a, b, c) in t.get_difficulty_breakdown(course_id)],
        "verdict_distribution": [
            {"verdict": a, "count": b} for (a, b) in e.get_verdict_distribution(course_id)],
        "lab_funnel": [
            {"id": a, "number": b, "title": c, "enrolled": d, "submitted": s, "approved": ap, "rejected": rj}
            for (a, b, c, d, s, ap, rj) in r.get_lab_funnel(course_id)],
        "verification": [
            {"decision": d, "decided_by": by, "count": n, "avg_ms": float(ms or 0), "avg_llm_calls": float(c or 0)}
            for (d, by, n, ms, c) in r.get_verification_stats(course_id=course_id)],
    }
