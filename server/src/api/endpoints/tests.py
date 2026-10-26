from fastapi import Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from agents.test_generator.service import TestService, TestServiceError
from auth import CurrentUser, ensure_course_access, require_student
from common.text_extraction import extract_text_from_bytes

from ..app import app

_service = TestService()


class GenerateModel(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    num_questions: int = Field(default=5, ge=1, le=20)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class SubmitModel(BaseModel):
    answers: list[str]


@app.post("/api/v1/courses/{course_id}/tests/generate", tags=["Тестирование"])
def generate_test(course_id: int, payload: GenerateModel, user: CurrentUser = Depends(require_student)):
    ensure_course_access(user, course_id)
    try:
        return _service.generate_by_topic(student_id=user.id, course_id=course_id, topic=payload.topic,
                                          num_questions=payload.num_questions, difficulty=payload.difficulty)
    except TestServiceError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/v1/courses/{course_id}/tests/generate-from-file", tags=["Тестирование"])
async def generate_test_from_file(
    course_id: int,
    file: UploadFile = File(...),
    num_questions: int = Form(default=5, ge=1, le=20),
    difficulty: str = Form(default="medium", pattern="^(easy|medium|hard)$"),
    user: CurrentUser = Depends(require_student),
):
    ensure_course_access(user, course_id)
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(400, "Файл больше 15 МБ")
    material = extract_text_from_bytes(data, file.filename or "material")
    try:
        return _service.generate_by_material(student_id=user.id, course_id=course_id, material=material,
                                             filename=file.filename or "файл",
                                             num_questions=num_questions, difficulty=difficulty)
    except TestServiceError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/v1/tests/{test_id}/submit", tags=["Тестирование"])
def submit_test(test_id: str, payload: SubmitModel, user: CurrentUser = Depends(require_student)):
    try:
        return _service.submit(test_id=test_id, student_id=user.id, answers=payload.answers)
    except TestServiceError as exc:
        raise HTTPException(400, str(exc))
