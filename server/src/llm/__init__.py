"""Слой доступа к нейросетевым моделям (LLM и эмбеддинги).

Все компоненты системы получают модели только через этот пакет, поэтому
провайдер (OpenRouter, NVIDIA API, любой OpenAI-совместимый сервис или заглушка для
тестов) заменяется изменением переменных окружения без правки кода.
"""
from .chat import get_chat_model, invoke_text
from .embeddings import embed_documents, embed_query
from .json_utils import extract_json

__all__ = ["get_chat_model", "invoke_text", "embed_documents", "embed_query", "extract_json"]
