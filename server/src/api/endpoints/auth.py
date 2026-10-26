from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from auth import CurrentUser, create_token, get_current_user, hash_password, needs_rehash, verify_password
from constants import PREDEFINED_TAGS
from database.sql import RecommendationRepository, StudentRepository, TeacherRepository

from ..app import app


class LoginModel(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)
    role: Literal["student", "teacher"]


class RegisterTeacherModel(BaseModel):
    login: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=4, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class RegisterStudentModel(RegisterTeacherModel):
    characteristic: str | None = Field(default=None, max_length=2000)
    interests: list[str] = []


def _session(user_id: int, role: str, first: str, last: str) -> dict:
    name = f"{first} {last}"
    return {"token": create_token(user_id, role, name), "role": role, "id": user_id, "name": name}


@app.post("/api/v1/auth/login", tags=["Авторизация"])
def login(payload: LoginModel):
    repo = StudentRepository() if payload.role == "student" else TeacherRepository()
    creds = repo.get_credentials(payload.login.strip())
    if not creds or not verify_password(payload.password, creds[1]):
        raise HTTPException(401, "Неверный логин или пароль")
    user_id, stored = creds
    if needs_rehash(stored):  # перенос старых учётных записей на хеширование
        repo.set_password_hash(user_id, hash_password(payload.password))
    first, last = repo.get_first_and_last_names(user_id)
    return _session(user_id, payload.role, first, last)


@app.post("/api/v1/auth/register/student", tags=["Авторизация"])
def register_student(payload: RegisterStudentModel):
    repo = StudentRepository()
    if repo.is_login_already_used(payload.login.strip()):
        raise HTTPException(409, "Логин уже занят")
    invalid = [t for t in payload.interests if t not in PREDEFINED_TAGS]
    if invalid:
        raise HTTPException(400, f"Неизвестные теги: {invalid}")
    student_id = repo.create(
        login=payload.login.strip(), password=hash_password(payload.password),
        first_name=payload.first_name.strip(), last_name=payload.last_name.strip(),
        characteristic=(payload.characteristic or "").strip() or None,
    )
    if payload.interests:
        RecommendationRepository().set_student_interests(student_id, payload.interests)
    return _session(student_id, "student", payload.first_name.strip(), payload.last_name.strip())


@app.post("/api/v1/auth/register/teacher", tags=["Авторизация"])
def register_teacher(payload: RegisterTeacherModel):
    repo = TeacherRepository()
    if repo.is_login_already_used(payload.login.strip()):
        raise HTTPException(409, "Логин уже занят")
    teacher_id = repo.create(
        login=payload.login.strip(), password=hash_password(payload.password),
        first_name=payload.first_name.strip(), last_name=payload.last_name.strip(),
    )
    return _session(teacher_id, "teacher", payload.first_name.strip(), payload.last_name.strip())


@app.get("/api/v1/auth/me", tags=["Авторизация"])
def whoami(user: CurrentUser = Depends(get_current_user)):
    return {"id": user.id, "role": user.role, "name": user.name}
