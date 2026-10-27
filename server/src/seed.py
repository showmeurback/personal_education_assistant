"""Наполнение базы демонстрационными данными вручную.

Запуск в контейнере:  docker compose exec backend python src/seed.py [--reset]

Без флага данные создаются, только если их ещё нет; с --reset демонстрационные
пользователи и курсы удаляются и создаются заново (данные других пользователей
не затрагиваются). При SEED_DEMO=true то же самое выполняется автоматически
при первом запуске сервера.
"""
import sys

import log  # noqa: F401
from demo.seed import ensure_materials, run

if __name__ == "__main__":
    created = run(reset="--reset" in sys.argv)
    print("Данные созданы." if created else "Демонстрационные данные уже есть (для пересоздания: --reset).")
    left = ensure_materials(attempts=1)
    print("Лекции курсов проиндексированы." if not left else f"Курсов без лекций: {left} (проверьте ключ эмбеддингов).")
    print("Вход: teacher1/teacher1, teacher2/teacher2, student1/student1 … student10/student10")
