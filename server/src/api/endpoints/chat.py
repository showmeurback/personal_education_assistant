from fastapi import Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from auth import CurrentUser, ensure_course_access, require_student
from database.sql import CourseRepository
from database.sql.repositories import ChatRepository
from rag.chain import ask

from ..app import app


class CreateChatModel(BaseModel):
    course_id: int
    name: str = Field(default="Новый чат", max_length=120)


class MessageModel(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class RenameModel(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _own_chat(chat_id: int, user: CurrentUser) -> tuple:
    chat = ChatRepository().get_chat(chat_id)
    if not chat or chat[1] != user.id:
        raise HTTPException(404, "Чат не найден")
    return chat


@app.post("/api/v1/chats", tags=["Чат"])
def create_chat(payload: CreateChatModel, user: CurrentUser = Depends(require_student)):
    ensure_course_access(user, payload.course_id)
    if not CourseRepository().get_storage_id(payload.course_id):
        raise HTTPException(400, "Преподаватель ещё не загрузил материалы курса — ассистенту не на что опираться")
    chat_id = ChatRepository().create_chat(user.id, payload.course_id, payload.name.strip() or "Новый чат")
    return {"chat_id": chat_id, "name": payload.name}


@app.get("/api/v1/me/chats", tags=["Чат"])
def my_chats(user: CurrentUser = Depends(require_student)):
    rows = ChatRepository().get_student_chats(user.id)
    return [{"chat_id": cid, "name": name, "course_id": course_id, "course_title": title, "created_at": created}
            for (cid, name, course_id, title, created) in rows]


@app.delete("/api/v1/chats/{chat_id}", tags=["Чат"])
def delete_chat(chat_id: int, user: CurrentUser = Depends(require_student)):
    _own_chat(chat_id, user)
    ChatRepository().delete_chat(chat_id)
    return {"success": True}


@app.patch("/api/v1/chats/{chat_id}", tags=["Чат"])
def rename_chat(chat_id: int, payload: RenameModel, user: CurrentUser = Depends(require_student)):
    _own_chat(chat_id, user)
    ChatRepository().rename_chat(chat_id, payload.name.strip())
    return {"success": True, "name": payload.name.strip()}


@app.get("/api/v1/chats/{chat_id}/messages", tags=["Чат"])
def get_messages(chat_id: int, user: CurrentUser = Depends(require_student)):
    _own_chat(chat_id, user)
    return [{"role": role, "content": content} for (role, content) in ChatRepository().get_messages(chat_id, limit=200)]


@app.post("/api/v1/chats/{chat_id}/messages", tags=["Чат"])
async def send_message(chat_id: int, payload: MessageModel, user: CurrentUser = Depends(require_student)):
    _, student_id, course_id, name, _ = _own_chat(chat_id, user)
    storage_id = CourseRepository().get_storage_id(course_id)
    if not storage_id:
        raise HTTPException(400, "У курса нет загруженных материалов")
    repo = ChatRepository()
    history = []
    for role, content in repo.get_messages(chat_id, limit=20):
        history.append(HumanMessage(content=content) if role == "human" else AIMessage(content=content))
    result = await run_in_threadpool(ask, storage_id, payload.message, history, student_id, course_id, chat_id)
    repo.add_message(chat_id, "human", payload.message)
    repo.add_message(chat_id, "ai", result["response"])
    if name == "Новый чат" and not history:
        title = payload.message.strip().replace("\n", " ")
        repo.rename_chat(chat_id, title[:60] + ("…" if len(title) > 60 else ""))
    return result
