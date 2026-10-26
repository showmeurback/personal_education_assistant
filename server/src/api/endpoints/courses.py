from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from auth import (CurrentUser, ensure_course_access, ensure_course_owner, get_current_user,
                  require_student, require_teacher)
from constants import PREDEFINED_TAGS
from database.sql import CourseRepository, RecommendationRepository
from database.vector.repositories import StorageManager
from models.course import NewCourse

from ..app import app

DIFFICULTIES = {"beginner", "intermediate", "advanced"}


class CourseModel(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    difficulty: str = "intermediate"
    tags: list[str] = []
    exam_questions: str = Field(default="", max_length=20000)


def _validate(payload: CourseModel) -> None:
    if payload.difficulty not in DIFFICULTIES:
        raise HTTPException(400, "Неизвестный уровень сложности")
    invalid = [t for t in payload.tags if t not in PREDEFINED_TAGS]
    if invalid:
        raise HTTPException(400, f"Неизвестные теги: {invalid}")


@app.post("/api/v1/courses", tags=["Курсы"])
def create_course(payload: CourseModel, user: CurrentUser = Depends(require_teacher)):
    _validate(payload)
    course_id = CourseRepository().create(NewCourse(
        title=payload.title.strip(), teacher_id=user.id, exam_questions=payload.exam_questions,
        description=payload.description, difficulty=payload.difficulty, tags=payload.tags,
    ))
    if payload.tags:
        RecommendationRepository().set_course_tags(course_id, payload.tags)
    return {"success": True, "course_id": course_id}


@app.get("/api/v1/courses", tags=["Курсы"])
def list_courses(user: CurrentUser = Depends(get_current_user)):
    repo = CourseRepository()
    tags_map = RecommendationRepository().get_all_course_tags()
    enrolled = set()
    if user.is_student:
        enrolled = {cid for cid, _ in repo.get_student_courses(user.id)}
    return [
        {
            "id": cid, "title": title, "teacher_id": teacher_id, "description": description,
            "difficulty": difficulty, "created_at": str(created_at) if created_at else None,
            "tags": tags_map.get(cid, []), "enrolled": cid in enrolled,
        }
        for (cid, title, teacher_id, description, difficulty, created_at) in repo.list_all()
    ]


@app.get("/api/v1/courses/{course_id}", tags=["Курсы"])
def get_course(course_id: int, user: CurrentUser = Depends(get_current_user)):
    repo = CourseRepository()
    info = repo.get_course_info(course_id)
    if not info:
        raise HTTPException(404, "Курс не найден")
    cid, title, teacher_id, exam_questions, storage_id, description, difficulty, created_at = info[0]
    is_owner = user.is_teacher and user.id == teacher_id
    data = {
        "id": cid, "title": title, "teacher_id": teacher_id, "description": description,
        "difficulty": difficulty, "created_at": str(created_at) if created_at else None,
        "tags": RecommendationRepository().get_course_tags(course_id),
        "has_materials": bool(storage_id), "is_owner": is_owner,
    }
    if is_owner:
        data["exam_questions"] = exam_questions
    if user.is_student:
        data["enrolled"] = repo.is_enrolled(user.id, course_id)
        data["request_status"] = repo.get_request_status(user.id, course_id)
    return data


@app.put("/api/v1/courses/{course_id}", tags=["Курсы"])
def update_course(course_id: int, payload: CourseModel, user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    _validate(payload)
    CourseRepository().update(
        course_id, title=payload.title.strip(), exam_questions=payload.exam_questions,
        description=payload.description, difficulty=payload.difficulty,
    )
    RecommendationRepository().set_course_tags(course_id, payload.tags)
    return {"success": True}


@app.delete("/api/v1/courses/{course_id}", tags=["Курсы"])
def delete_course(course_id: int, user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    repo = CourseRepository()
    storage_id = repo.get_storage_id(course_id)
    if storage_id:
        StorageManager.delete_storage(storage_id)
    repo.delete(course_id)
    return {"success": True}


@app.get("/api/v1/courses/{course_id}/students", tags=["Курсы"])
def course_students(course_id: int, user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    rows = CourseRepository().get_students(course_id)
    return {"students": [{"id": i, "first_name": f, "last_name": l} for (i, f, l) in rows]}


# ── Заявки на курс ─────────────────────────────────────────────────────────────

@app.post("/api/v1/courses/{course_id}/requests", tags=["Курсы"])
def create_course_request(course_id: int, user: CurrentUser = Depends(require_student)):
    repo = CourseRepository()
    if repo.get_owner(course_id) is None:
        raise HTTPException(404, "Курс не найден")
    if repo.is_enrolled(user.id, course_id):
        raise HTTPException(409, "Вы уже записаны на этот курс")
    request_id = repo.create_course_request(student_id=user.id, course_id=course_id)
    return {"success": True, "request_id": request_id}


@app.get("/api/v1/courses/{course_id}/requests", tags=["Курсы"])
def get_course_requests(course_id: int, user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    rows = CourseRepository().get_course_requests(course_id)
    return {"requests": [
        {"id": rid, "student_id": sid, "course_id": cid, "status": status, "created_at": created_at,
         "first_name": first, "last_name": last}
        for (rid, sid, cid, status, created_at, first, last) in rows
    ]}


def _request_for_owner(request_id: int, user: CurrentUser) -> tuple[int, int, str]:
    row = CourseRepository().get_course_request_by_id(request_id)
    if not row:
        raise HTTPException(404, "Заявка не найдена")
    ensure_course_owner(user, row[1])
    return row


@app.post("/api/v1/course-requests/{request_id}/approve", tags=["Курсы"])
def approve_course_request(request_id: int, user: CurrentUser = Depends(require_teacher)):
    student_id, course_id, _ = _request_for_owner(request_id, user)
    repo = CourseRepository()
    repo.enroll_student(student_id=student_id, course_id=course_id)
    repo.set_course_request_status(request_id, "approved")
    return {"success": True}


@app.post("/api/v1/course-requests/{request_id}/reject", tags=["Курсы"])
def reject_course_request(request_id: int, user: CurrentUser = Depends(require_teacher)):
    _request_for_owner(request_id, user)
    CourseRepository().set_course_request_status(request_id, "rejected")
    return {"success": True}
