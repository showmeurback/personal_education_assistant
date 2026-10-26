"""Получение материала для генерации теста из базы знаний курса (Weaviate)."""
from __future__ import annotations

from typing import Optional, Tuple

from database.sql import CourseRepository
from database.vector.repositories import StorageManager
from log import logger


class MaterialProvider:
    def get_validated_material(self, topic: str, course_id: Optional[int] = None
                               ) -> Tuple[bool, Optional[str], str]:
        if not topic or not topic.strip():
            return False, None, "Тема не может быть пустой"
        if not course_id:
            return False, None, "Не указан курс для поиска материалов"
        storage_id = CourseRepository().get_storage_id(course_id)
        if not storage_id:
            return False, None, "Преподаватель ещё не загрузил материалы курса"
        try:
            store = StorageManager.get_vector_storage(storage_id)
            chunks = store.hybrid_search(topic.strip(), k=8, alpha=0.6)
        except ValueError:
            return False, None, "Векторное хранилище курса не найдено"
        except Exception as exc:
            logger.error(f"Поиск материалов не удался: {exc}")
            return False, None, "Сервис поиска по материалам временно недоступен"

        # символьный фильтр релевантности: отбрасываем фрагменты с низким
        # комбинированным баллом гибридного поиска
        relevant = [c for c in chunks if c.score is None or c.score >= 0.3] or chunks[:3]
        material = "\n\n".join(c.text for c in relevant)
        if len(material.strip()) < 200:
            return False, None, f"По теме «{topic}» в материалах курса недостаточно информации"
        return True, material, f"Найдено фрагментов: {len(relevant)}"
