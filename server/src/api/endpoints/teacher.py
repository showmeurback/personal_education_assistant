from fastapi import Depends

from auth import CurrentUser, require_teacher
from database.sql import CourseRepository, RecommendationRepository
from database.sql.repositories.reports import ReportRepository

from ..app import app


@app.get("/api/v1/teacher/courses", tags=["Преподаватель"])
def teacher_courses(user: CurrentUser = Depends(require_teacher)):
    tags_map = RecommendationRepository().get_all_course_tags()
    return [
        {"id": cid, "title": title, "description": description, "difficulty": difficulty,
         "created_at": created_at, "tags": tags_map.get(cid, []), "students": students,
         "pending_requests": requests, "pending_reports": reports}
        for (cid, title, description, difficulty, created_at, students, requests, reports)
        in CourseRepository().get_teacher_courses_detailed(user.id)
    ]


@app.get("/api/v1/teacher/reports/queue", tags=["Преподаватель"])
def teacher_queue(user: CurrentUser = Depends(require_teacher)):
    repo = ReportRepository()
    reports = repo.get_teacher_queue(user.id)
    for r in reports:
        check = repo.get_check(r["report_id"])
        r["check"] = None if check is None else {k: v for k, v in check.items() if k != "protocol"}
    return {"reports": reports}


@app.get("/api/v1/teacher/reports/history", tags=["Преподаватель"])
def teacher_history(user: CurrentUser = Depends(require_teacher)):
    return {"reports": ReportRepository().get_teacher_history(user.id)}


@app.get("/api/v1/teacher/verification-stats", tags=["Преподаватель"])
def verification_stats(user: CurrentUser = Depends(require_teacher)):
    rows = ReportRepository().get_verification_stats(teacher_id=user.id)
    return {"stats": [
        {"decision": d, "decided_by": by, "count": n, "avg_ms": float(ms or 0), "avg_llm_calls": float(c or 0)}
        for (d, by, n, ms, c) in rows
    ]}
