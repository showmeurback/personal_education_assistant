from loguru import logger
from langchain_core.tools import tool

from rag.queries import query_search_materials


def make_search_tool(storage_id: str, sources: list[str]):
    @tool
    def search_course_materials(query: str) -> str:
        """
        Гибридный поиск по материалам курса (BM25 + векторный поиск).
        Вызывай для любого учебного вопроса: объяснить тему, дать определение, найти правильный ответ,
        разобрать понятие из курса. Не отвечай на учебные вопросы по памяти — всегда ищи через этот инструмент.
        Возвращает релевантные фрагменты из загруженных материалов курса с указанием файла-источника.
        """
        logger.debug(f"    → search_course_materials(query='{query[:80]}')")
        try:
            chunks = query_search_materials(storage_id, query)
        except Exception as e:
            logger.error(f"    ← search_course_materials ERROR: {e}")
            return "Поиск по материалам временно недоступен."
        if not chunks:
            return "По запросу ничего не найдено в материалах курса."
        parts = []
        for c in chunks:
            if c["filename"] and c["filename"] not in sources:
                sources.append(c["filename"])
            parts.append(f"[Источник: {c['filename'] or 'материал курса'}]\n{c['text']}")
        return "\n\n---\n\n".join(parts)

    return search_course_materials
