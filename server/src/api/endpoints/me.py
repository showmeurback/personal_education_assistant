"""Данные текущего студента."""
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from auth import CurrentUser, require_student
from constants import PREDEFINED_TAGS
from database.sql import (CourseRepository, RecommendationRepository, StudentPreferencesRepository,
                          StudentRepository)
from database.sql.repositories.reports import ReportRepository

from ..app import app


class PreferencesModel(BaseModel):
    preferred_explanation_style: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2000)


class InterestsModel(BaseModel):
    interests: list[str]


class CharacteristicModel(BaseModel):
    characteristic: str = Field(default="", max_length=2000)


@app.get("/api/v1/me/profile", tags=["Профиль"])
def my_profile(user: CurrentUser = Depends(require_student)):
    row = StudentRepository().get_by_id(user.id)
    if not row:
        raise HTTPException(404, "Студент не найден")
    _id, login, first_name, last_name, characteristic = row
    return {"id": _id, "login": login, "first_name": first_name, "last_name": last_name,
            "characteristic": characteristic}


@app.put("/api/v1/me/characteristic", tags=["Профиль"])
def update_characteristic(payload: CharacteristicModel, user: CurrentUser = Depends(require_student)):
    StudentRepository().update_characteristic(user.id, payload.characteristic.strip())
    return {"success": True}


@app.get("/api/v1/me/preferences", tags=["Профиль"])
def my_preferences(user: CurrentUser = Depends(require_student)):
    prefs = StudentPreferencesRepository().get_preferences(user.id) or {}
    return {"preferred_explanation_style": prefs.get("preferred_explanation_style"),
            "notes": prefs.get("notes")}


@app.put("/api/v1/me/preferences", tags=["Профиль"])
def update_my_preferences(payload: PreferencesModel, user: CurrentUser = Depends(require_student)):
    StudentPreferencesRepository().update_preferences(
        user.id, payload.preferred_explanation_style, payload.notes)
    return {"success": True}


@app.get("/api/v1/me/interests", tags=["Профиль"])
def my_interests(user: CurrentUser = Depends(require_student)):
    return {"interests": RecommendationRepository().get_student_interests(user.id)}


@app.put("/api/v1/me/interests", tags=["Профиль"])
def update_my_interests(payload: InterestsModel, user: CurrentUser = Depends(require_student)):
    invalid = [t for t in payload.interests if t not in PREDEFINED_TAGS]
    if invalid:
        raise HTTPException(400, f"Неизвестные теги: {invalid}")
    RecommendationRepository().set_student_interests(user.id, payload.interests)
    return {"success": True}


@app.get("/api/v1/me/courses", tags=["Профиль"])
def my_courses(user: CurrentUser = Depends(require_student)):
    rows = CourseRepository().get_student_courses_detailed(user.id)
    rec = RecommendationRepository()
    tags_map = rec.get_all_course_tags()
    return [
        {
            "id": cid, "title": title, "description": description, "difficulty": difficulty,
            "created_at": created_at, "tags": tags_map.get(cid, []),
            "labs_completed": bool(labs_completed), "exam_completed": bool(exam_completed),
            "is_completed": bool(labs_completed) and bool(exam_completed),
            "my_rating": rec.get_course_rating(student_id=user.id, course_id=cid),
        }
        for (cid, title, description, difficulty, created_at, labs_completed, exam_completed) in rows
    ]


@app.get("/api/v1/me/reports", tags=["Профиль"])
def my_reports(user: CurrentUser = Depends(require_student)):
    return {"reports": ReportRepository().get_student_reports(user.id)}
