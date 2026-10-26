from .app import app
from .endpoints import (  # noqa: F401 — регистрация маршрутов
    auth,
    me,
    teacher,
    courses,
    course_files,
    labs,
    reports,
    tests,
    exam,
    chat,
    results,
    recommendations,
    system,
    progress,
)
