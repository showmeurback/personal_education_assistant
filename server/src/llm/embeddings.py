"""Получение векторных представлений текста.

Провайдеры:
  openrouter, openai — OpenAI-совместимый /embeddings;
  nvidia — NVIDIA API Catalog (тот же протокол плюс параметр input_type для асимметричных моделей);
  local  — контейнер t2v-transformers (используется при отсутствии доступа к API);
  hash   — детерминированные «хеш-эмбеддинги» для тестов (без сети).
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from functools import lru_cache

import requests

from settings import embedding_settings as cfg


class EmbeddingError(RuntimeError):
    pass


def embed_documents(texts: list[str], *, timeout: float = 60.0, attempts: int = 3) -> list[list[float]]:
    """Эмбеддинги фрагментов документов (passage).

    Сетевые ошибки и тайм-ауты поставщика превращаются в EmbeddingError, который
    API отдаёт пользователю как «сервис временно недоступен» (503), а не как 500.
    """
    return _embed(texts, input_type="passage", timeout=timeout, attempts=attempts)


def embed_query(text: str) -> list[float]:
    """Эмбеддинг поискового запроса (query). Результат кэшируется."""
    return list(_embed_query_cached(text))


@lru_cache(maxsize=2048)
def _embed_query_cached(text: str) -> tuple[float, ...]:
    return tuple(_embed([text], input_type="query")[0])


def _embed(texts: list[str], input_type: str, timeout: float = 60.0, attempts: int = 3) -> list[list[float]]:
    if not texts:
        return []
    provider = cfg.provider.lower()
    if provider == "hash":
        return [_hash_embedding(t, cfg.hash_dim) for t in texts]
    if provider == "local":
        try:
            return [_local_embedding(t) for t in texts]
        except requests.RequestException as exc:
            raise EmbeddingError(f"локальная модель эмбеддингов недоступна: {type(exc).__name__}") from exc
    if provider in ("nvidia", "openrouter", "openai"):
        out: list[list[float]] = []
        for i in range(0, len(texts), cfg.batch_size):
            out.extend(_api_batch(texts[i:i + cfg.batch_size], input_type, nvidia=provider == "nvidia",
                                  timeout=timeout, attempts=attempts))
        return out
    raise EmbeddingError(f"Неизвестный провайдер эмбеддингов: {cfg.provider}")


def _api_batch(texts: list[str], input_type: str, nvidia: bool, timeout: float = 60.0,
               attempts: int = 3) -> list[list[float]]:
    if not cfg.api_key:
        raise EmbeddingError("Не задан ключ API для эмбеддингов (LLM_API_KEY или EMBEDDING_API_KEY).")
    payload = {"input": [t if t.strip() else " " for t in texts], "model": cfg.model, "encoding_format": "float"}
    if nvidia:
        payload.update({"input_type": input_type, "truncate": "END"})
    # перегрузка сервиса (429/5xx) или зависший запрос — повтор с ожиданием
    last = attempts - 1
    for attempt in range(attempts):
        try:
            resp = requests.post(
                f"{cfg.base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {cfg.api_key}", "Accept": "application/json"},
                json=payload,
                timeout=timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == last:
                raise EmbeddingError(f"сервис не ответил ({type(exc).__name__})") from exc
            time.sleep(5 * (attempt + 1))
            continue
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < last:
            time.sleep(5 * (attempt + 1))
            continue
        break
    if resp.status_code != 200:
        raise EmbeddingError(f"Ошибка API эмбеддингов {resp.status_code}: {resp.text[:300]}")
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def _local_embedding(text: str) -> list[float]:
    resp = requests.post(f"{cfg.local_url.rstrip('/')}/vectors", json={"text": text}, timeout=30)
    if resp.status_code != 200:
        raise EmbeddingError(f"t2v-transformers недоступен: {resp.status_code}")
    return resp.json()["vector"]


_TOKEN = re.compile(r"\w+", re.UNICODE)


def _hash_embedding(text: str, dim: int) -> list[float]:
    """Векторизация «мешка» усечённых слов через хеширование признаков (feature hashing)."""
    vec = [0.0] * dim
    for token in _TOKEN.findall(text.lower()):
        stem = token[:6]
        h = int(hashlib.md5(stem.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 64) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
