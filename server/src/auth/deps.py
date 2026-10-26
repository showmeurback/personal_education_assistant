"""Зависимости FastAPI для аутентификации и проверки прав доступа.

Прежняя версия API принимала идентификатор пользователя из запроса и не
проверяла его — любой клиент мог читать и изменять чужие данные. Теперь
пользователь определяется только по подписанному токену.
"""
from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database.sql.repositories.courses import CourseRepository
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str  # "student" | "teacher"
    name: str = ""

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Срок действия сессии истёк")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный токен")
    return CurrentUser(id=int(payload["sub"]), role=payload["role"], name=payload.get("name", ""))


def require_student(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_student:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только студентам")
    return user


def require_teacher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_teacher:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только преподавателям")
    return user


def ensure_self_student(user: CurrentUser, student_id: int) -> None:
    """Студент обращается к собственным данным."""
    if not (user.is_student and user.id == student_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к данным другого пользователя")


def ensure_course_owner(user: CurrentUser, course_id: int) -> None:
    """Преподаватель — владелец курса."""
    if not user.is_teacher:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только преподавателю курса")
    owner = CourseRepository().get_owner(course_id)
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Курс не найден")
    if owner != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Курс принадлежит другому преподавателю")


def ensure_course_access(user: CurrentUser, course_id: int) -> None:
    """Доступ к содержимому курса: владелец-преподаватель или зачисленный студент."""
    repo = CourseRepository()
    owner = repo.get_owner(course_id)
    if owner is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Курс не найден")
    if user.is_teacher and owner == user.id:
        return
    if user.is_student and repo.is_enrolled(user.id, course_id):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к курсу")
