import time

import log  # noqa: F401 — настраивает loguru до всех остальных импортов
from log import logger
from api.server import start_server
from database.sql import Database as SQLDatabase
from database.vector import VecDatabase


def _retry(name: str, func, attempts: int = 30, delay: float = 2.0) -> None:
    for attempt in range(1, attempts + 1):
        try:
            func()
            return
        except Exception as exc:
            logger.warning(f"{name} недоступен (попытка {attempt}/{attempts}): {exc}")
            time.sleep(delay)
    raise RuntimeError(f"{name} так и не стал доступен")


if __name__ == "__main__":
    _retry("PostgreSQL", SQLDatabase().create_tables)
    _retry("Weaviate", VecDatabase().init_db)
    from settings import settings
    if settings.seed_demo:  # пустая база наполняется демонстрационными данными в фоне
        import threading

        from demo.seed import auto_seed
        threading.Thread(target=auto_seed, name="demo-seed", daemon=True).start()
    start_server()
