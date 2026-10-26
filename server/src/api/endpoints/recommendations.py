from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from auth import CurrentUser, get_current_user, require_student, require_teacher, ensure_course_owner
from constants import PREDEFINED_TAGS
from database.sql import CourseRepository, RecommendationRepository
from recommendations import RecommendationService

from ..app import app


class RateModel(BaseModel):
    rating: int = Field(ge=1, le=5)


@app.get("/api/v1/tags", tags=["Рекомендации"])
def get_available_tags(user: CurrentUser = Depends(get_current_user)):
    return {"tags": PREDEFINED_TAGS}


@app.get("/api/v1/me/recommendations", tags=["Рекомендации"])
def my_recommendations(user: CurrentUser = Depends(require_student)):
    interests = RecommendationRepository().get_student_interests(user.id)
    courses = RecommendationService().get_ranked_courses(user.id)
    recommended, other = [], courses
    if interests and courses:
        top = [c for c in courses[:3] if c["tag_match"] > 0 or c["signals"]["semantic"] > 0.02]
        if top and top[0]["score"] > 0.25:
            recommended = top
            ids = {c["id"] for c in top}
            other = [c for c in courses if c["id"] not in ids]
    return {
        "recommended": recommended,
        "other": other,
        "has_recommendations": bool(recommended),
        "maybe_like": other[0] if other else None,
    }


@app.post("/api/v1/courses/{course_id}/rate", tags=["Рекомендации"])
def rate_course(course_id: int, payload: RateModel, user: CurrentUser = Depends(require_student)):
    if not CourseRepository().is_enrolled(user.id, course_id):
        raise HTTPException(403, "Оценить можно только курс, на который вы записаны")
    RecommendationRepository().rate_course(student_id=user.id, course_id=course_id, rating=payload.rating)
    return {"success": True}
