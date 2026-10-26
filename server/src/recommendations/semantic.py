"""Семантический сигнал рекомендаций: близость характеристики студента и описаний курсов.

Векторы получаются через общий слой эмбеддингов (llm.embeddings). Векторы
описаний кэшируются по хешу текста, поэтому повторный запрос рекомендаций
не обращается к модели заново. При недоступности модели сигнал не
учитывается (вклад равен нулю), а остальные сигналы работают как прежде.
"""
from __future__ import annotations

import hashlib
import threading

from llm.embeddings import cosine_similarity, embed_documents, embed_query
from log import logger

_cache: dict[str, list[float]] = {}
_lock = threading.Lock()


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _description_vectors(texts: list[str]) -> list[list[float]]:
    missing = [t for t in texts if _key(t) not in _cache]
    if missing:
        vectors = embed_documents(missing)
        with _lock:
            for t, v in zip(missing, vectors):
                _cache[_key(t)] = v
    return [_cache[_key(t)] for t in texts]


def get_semantic_scores(characteristic: str | None, course_descriptions: dict[int, str]) -> dict[int, float]:
    if not characteristic or not characteristic.strip() or not course_descriptions:
        return {}
    items = [(cid, d) for cid, d in course_descriptions.items() if d and d.strip()]
    if not items:
        return {}
    try:
        query_vec = embed_query(characteristic)
        vectors = _description_vectors([d for _, d in items])
    except Exception as exc:
        logger.warning(f"Семантический сигнал отключён: {exc}")
        return {}
    return {cid: max(0.0, cosine_similarity(query_vec, vec)) for (cid, _), vec in zip(items, vectors)}
