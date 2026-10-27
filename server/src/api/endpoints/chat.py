import json
import queue
import threading
import time

from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from auth import CurrentUser, ensure_course_access, require_student
from database.sql import CourseRepository
from database.sql.repositories import ChatRepository
from log import logger
from rag.chain import ask, stream_ask

from ..app import app

STREAM_ATTEMPTS = 3      # попыток потокового ответа при перегрузке провайдера
STREAM_RETRY_DELAY = 3.0  # с; пауза растёт с номером попытки


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


def _history_and_storage(chat_id: int, user: CurrentUser) -> tuple[list, str, int, str]:
    _, student_id, course_id, name, _ = _own_chat(chat_id, user)
    storage_id = CourseRepository().get_storage_id(course_id)
    if not storage_id:
        raise HTTPException(400, "У курса нет загруженных материалов")
    history = []
    for role, content in ChatRepository().get_messages(chat_id, limit=20):
        history.append(HumanMessage(content=content) if role == "human" else AIMessage(content=content))
    return history, storage_id, course_id, name


def _save_exchange(chat_id: int, name: str, had_history: bool, question: str, answer: str) -> None:
    repo = ChatRepository()
    repo.add_message(chat_id, "human", question)
    repo.add_message(chat_id, "ai", answer)
    if name == "Новый чат" and not had_history:
        title = question.strip().replace("\n", " ")
        repo.rename_chat(chat_id, title[:60] + ("…" if len(title) > 60 else ""))


@app.post("/api/v1/chats/{chat_id}/messages", tags=["Чат"])
async def send_message(chat_id: int, payload: MessageModel, user: CurrentUser = Depends(require_student)):
    history, storage_id, course_id, name = _history_and_storage(chat_id, user)
    result = await run_in_threadpool(ask, storage_id, payload.message, history, user.id, course_id, chat_id)
    _save_exchange(chat_id, name, bool(history), payload.message, result["response"])
    return result


def _llm_error_text(exc: Exception) -> str:
    if type(exc).__module__.startswith("openai") or type(exc).__name__ in ("LLMUnavailableError",):
        return "Сервис языковой модели временно перегружен или недоступен. Повторите запрос через минуту."
    if type(exc).__name__ == "EmbeddingError":
        return f"Сервис эмбеддингов недоступен: {exc}"
    return "Не удалось получить ответ ассистента."


@app.post("/api/v1/chats/{chat_id}/messages/stream", tags=["Чат"])
def send_message_stream(chat_id: int, payload: MessageModel, user: CurrentUser = Depends(require_student)):
    """Потоковый ответ (Server-Sent Events): шаги агента и текст ответа по мере генерации.

    Агент работает в отдельном потоке и складывает события в очередь, поэтому, даже если
    студент закрыл страницу, ответ дописывается и сохраняется в истории диалога."""
    history, storage_id, course_id, name = _history_and_storage(chat_id, user)
    events: queue.Queue = queue.Queue()

    def work() -> None:
        # Перегрузка провайдера может прийти внутри уже начатого потока (HTTP 200), где встроенные
        # повторы клиента не срабатывают; поэтому весь ответ повторяется. Инструменты агента только
        # читают данные (кроме идемпотентного сохранения предпочтений), повтор безопасен.
        attempts = STREAM_ATTEMPTS
        try:
            for attempt in range(1, attempts + 1):
                try:
                    for event in stream_ask(storage_id, payload.message, history, user.id, course_id, chat_id):
                        if event["type"] == "done":
                            _save_exchange(chat_id, name, bool(history), payload.message, event["response"])
                        events.put(event)
                    return
                except Exception as exc:  # noqa: BLE001 — любая ошибка должна дойти до клиента событием
                    transient = type(exc).__module__.startswith("openai")
                    logger.warning(f"Потоковый ответ ассистента не получен (попытка {attempt}): "
                                   f"{type(exc).__name__}: {exc}")
                    if transient and attempt < attempts:
                        events.put({"type": "reset"})
                        events.put({"type": "step", "text": "Модель перегружена, повторяю запрос"})
                        time.sleep(STREAM_RETRY_DELAY * attempt)
                        continue
                    events.put({"type": "error", "detail": _llm_error_text(exc)})
                    return
        finally:
            events.put(None)

    threading.Thread(target=work, name=f"chat-{chat_id}", daemon=True).start()

    def sse():
        while True:
            try:
                event = events.get(timeout=15)
            except queue.Empty:
                yield ": ping\n\n"  # не даём прокси закрыть соединение во время долгого шага
                continue
            if event is None:
                return
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
