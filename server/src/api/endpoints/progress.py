from fastapi import Depends

from agents.progress.weak_topics import weak_topics
from auth import CurrentUser, ensure_course_access, require_student
from database.sql import CourseRepository

from ..app import app


@app.get("/api/v1/courses/{course_id}/weak-topics", tags=["Профиль"])
def course_weak_topics(course_id: int, advice: bool = True, user: CurrentUser = Depends(require_student)):
    """Карта пробелов студента по курсу: слабые темы с уровнем освоения, конкретными
    ошибками, советом по повторению и фрагментами лекций."""
    ensure_course_access(user, course_id)
    info = CourseRepository().get_course_info(course_id)
    title = info[0][1] if info else ""
    return weak_topics(user.id, course_id, title, with_advice=advice)
