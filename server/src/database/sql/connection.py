"""Подключение к PostgreSQL.

Декоратор postgre_connection выдаёт функции курсор из пула соединений,
фиксирует транзакцию при успехе и откатывает её при любой ошибке.
Ошибка пробрасывается дальше: молчаливый возврат None (как было раньше)
приводил к трудноуловимым отказам в вызывающем коде.
"""
from __future__ import annotations

import threading
from functools import wraps

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

from log import logger
from settings import PostgreDatabaseConfig

_pools: dict[tuple, ThreadedConnectionPool] = {}
_lock = threading.Lock()


def _get_pool(config: PostgreDatabaseConfig) -> ThreadedConnectionPool:
    key = (config.host, config.port, config.name, config.user)
    pool = _pools.get(key)
    if pool is None:
        with _lock:
            pool = _pools.get(key)
            if pool is None:
                pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=20,
                    host=config.host,
                    dbname=config.name,
                    user=config.user,
                    password=config.password,
                    port=config.port,
                )
                _pools[key] = pool
    return pool


def postgre_connection(config: PostgreDatabaseConfig):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if kwargs.get("curs") is not None:  # вложенный вызов в рамках той же транзакции
                return func(*args, **kwargs)
            pool = _get_pool(config)
            conn = pool.getconn()
            try:
                with conn.cursor() as cursor:
                    kwargs["curs"] = cursor
                    result = func(*args, **kwargs)
                conn.commit()
                return result
            except Exception as exc:
                conn.rollback()
                if isinstance(exc, psycopg2.Error):
                    logger.error(f"DB error in {func.__qualname__}: {exc}")
                raise
            finally:
                pool.putconn(conn)
        return inner
    return wrapper


def connect_to_postgresql(settings: PostgreDatabaseConfig):
    return psycopg2.connect(
        host=settings.host,
        dbname=settings.name,
        user=settings.user,
        password=settings.password,
        port=settings.port,
    )
