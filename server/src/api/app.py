import openai
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from common.text_extraction import ExtractionError, UnsupportedFileError
from llm.chat import LLMUnavailableError
from llm.embeddings import EmbeddingError
from log import logger

tags_metadata = [
    {"name": "Авторизация", "description": "Вход, регистрация, текущий пользователь"},
    {"name": "Профиль", "description": "Данные текущего студента: курсы, результаты, предпочтения"},
    {"name": "Курсы", "description": "Каталог, управление курсами, заявки, материалы"},
    {"name": "Лабораторные", "description": "Лабораторные работы и формальные требования к отчётам"},
    {"name": "Отчёты", "description": "Сдача отчётов и гибридная проверка с протоколом"},
    {"name": "Чат", "description": "RAG-ассистент по материалам курса"},
    {"name": "Экзамен", "description": "Пробный экзамен с LLM-экзаменатором"},
    {"name": "Тестирование", "description": "Генерация и проверка тестов"},
    {"name": "Преподаватель", "description": "Очередь проверки, статистика"},
    {"name": "Рекомендации", "description": "Теги, интересы, оценки, рекомендации курсов"},
    {"name": "Система", "description": "Состояние сервиса"},
]

app = FastAPI(
    title="Персональный ассистент по обучению — API",
    description="Гибридная интеллектуальная система: база знаний (PostgreSQL + Weaviate), "
                "символьные правила и SimHash, LLM-оценщики и RAG-агент.",
    version="2.0.0",
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMUnavailableError)
async def _llm_unavailable(_: Request, exc: LLMUnavailableError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(openai.APIConnectionError)
@app.exception_handler(openai.RateLimitError)
@app.exception_handler(openai.APIStatusError)
async def _llm_provider_error(_: Request, exc: Exception):
    logger.warning(f"Ошибка поставщика языковой модели: {exc}")
    return JSONResponse(status_code=503, content={
        "detail": "Сервис языковой модели временно перегружен или недоступен. Повторите запрос через минуту."})


@app.exception_handler(EmbeddingError)
async def _embedding_error(_: Request, exc: EmbeddingError):
    return JSONResponse(status_code=503, content={"detail": f"Сервис эмбеддингов недоступен: {exc}"})


@app.exception_handler(UnsupportedFileError)
@app.exception_handler(ExtractionError)
async def _extraction_error(_: Request, exc: Exception):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера"})
