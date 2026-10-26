"""Фабрика чат-моделей.

NVIDIA API Catalog, OpenRouter, Groq и другие поставщики совместимы с протоколом
OpenAI, поэтому используется единый клиент ChatOpenAI с изменённым base_url.
"""
from __future__ import annotations

import asyncio
import contextlib
import random
import time
from functools import lru_cache
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from settings import llm_settings


class LLMUnavailableError(RuntimeError):
    """Языковая модель не настроена или недоступна."""


def _content_to_text(content: Any) -> str:
    """Приводит content ответа модели к строке (часть моделей возвращает список блоков)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


@lru_cache(maxsize=32)
def get_chat_model(
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
    thinking: bool | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> BaseChatModel:
    """Возвращает (кэшированный) экземпляр чат-модели с заданными параметрами.

    thinking=False отключает этап рассуждения у гибридных моделей NVIDIA
    (chat_template_kwargs.enable_thinking) — ответ в несколько раз быстрее.
    """
    provider = llm_settings.provider.lower()
    temp = llm_settings.temperature if temperature is None else temperature
    if provider == "mock":
        from .mock import MockChatModel
        return MockChatModel()

    if not llm_settings.api_key:
        raise LLMUnavailableError(
            "Не задан ключ API (LLM_API_KEY). Укажите его в .env или выберите LLM_PROVIDER=mock."
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=llm_settings.base_url,
        api_key=llm_settings.api_key,
        model=model or llm_settings.model,
        temperature=temp,
        max_tokens=(max_tokens or llm_settings.max_tokens) + llm_settings.reasoning_reserve,
        timeout=timeout or llm_settings.timeout,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}}
        if thinking is False and provider == "nvidia" else None,
        max_retries=llm_settings.max_retries if max_retries is None else max_retries,
        # необязательные заголовки атрибуции OpenRouter; другими поставщиками игнорируются
        default_headers={"HTTP-Referer": "https://github.com/showmeurback/personal_education_assistant",
                         "X-Title": "Personal Education Assistant"} if provider == "openrouter" else None,
    )


def split_model(spec: str | None) -> tuple[str | None, bool | None]:
    """«модель@nothink» → (модель, thinking=False): гибридная модель без этапа рассуждения."""
    if not spec:
        return None, None
    name, _, flag = spec.partition("@")
    return name, (False if flag == "nothink" else None)


def _rate_limit_delay(exc: Exception, attempt: int) -> float | None:
    """Пауза перед повтором при превышении лимита (HTTP 429) или перегрузке (503); None — не повторять."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    transient = type(exc).__name__ in ("APIConnectionError", "APITimeoutError")  # обрыв сети, тайм-аут
    if status not in (429, 502, 503, 504) and not transient:
        return None
    retry_after = None
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    try:
        retry_after = float(headers.get("retry-after")) if headers.get("retry-after") else None
    except ValueError:
        retry_after = None
    base = retry_after if retry_after is not None else min(90.0, 10.0 * 2 ** attempt)
    return base + random.uniform(0, 2)


def _with_retries(call: Callable[[], Any]) -> Any:
    for attempt in range(llm_settings.rate_limit_retries + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001
            delay = _rate_limit_delay(exc, attempt)
            if delay is None or attempt == llm_settings.rate_limit_retries:
                raise
            time.sleep(delay)


_semaphores: dict[int, asyncio.Semaphore] = {}


def _semaphore() -> asyncio.Semaphore:
    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _semaphores:
        _semaphores[loop_id] = asyncio.Semaphore(max(1, llm_settings.max_concurrency))
    return _semaphores[loop_id]


def invoke_text(messages: list[BaseMessage] | str, **kwargs: Any) -> str:
    """Синхронный вызов модели с возвратом чистого текста."""
    model = get_chat_model(**kwargs)
    return _content_to_text(_with_retries(lambda: model.invoke(messages)).content)


async def ainvoke_text(messages: list[BaseMessage] | str, use_semaphore: bool = True,
                       retries: int | None = None, **kwargs: Any) -> str:
    """Асинхронный вызов модели с возвратом чистого текста.

    Число одновременных запросов ограничено LLM_MAX_CONCURRENCY, а при превышении
    лимита поставщика запрос повторяется с ожиданием. use_semaphore=False — вызывающий
    агент ограничивает параллельность сам (например, описание изображений).
    """
    model = get_chat_model(**kwargs)
    async with (_semaphore() if use_semaphore else contextlib.nullcontext()):
        limit = llm_settings.rate_limit_retries if retries is None else retries
        for attempt in range(limit + 1):
            try:
                response = await model.ainvoke(messages)
                return _content_to_text(response.content)
            except Exception as exc:  # noqa: BLE001
                delay = _rate_limit_delay(exc, attempt)
                if delay is None or attempt == limit:
                    raise
                await asyncio.sleep(delay)
    raise LLMUnavailableError("Превышено число повторов запроса к модели")
