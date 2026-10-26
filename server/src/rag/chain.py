import warnings
warnings.filterwarnings("ignore", message=".*create_react_agent.*")
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from llm.chat import _content_to_text, get_chat_model
from rag.tools import make_agent_tools
from database.sql.repositories.students import StudentRepository
from database.sql.repositories.courses import CourseRepository


def _build_system_prompt(student_name: str, course_title: str) -> str:
    return f"""\
Ты — AI-ассистент образовательной платформы по курсу «{course_title}».
Студент: {student_name}.

Правила поведения:
- Всегда отвечай на русском языке.
- Используй Markdown: заголовки, списки, таблицы, **жирный** для ключевых терминов.
- Формулы пиши обычным текстом (например, O(n log n), n^2), без LaTeX.
- Будь дружелюбен и поддерживай студента.
- Если для ответа нужны данные — вызывай инструменты сразу, не объясняя что собираешься делать.
- НЕ придумывай ответы из головы — опирайся на материалы курса.
- Если в материалах курса информации по теме нет совсем — честно сообщи: «К сожалению, в материалах курса информации по этой теме не найдено.»
- Если студент явно просит изменить стиль объяснения — вызови update_student_preferences, чтобы сохранить новый стиль именно для этого чата. Глобальные предпочтения из профиля не меняются.

Скилл «Объяснение темы или понятия» (ОБЯЗАТЕЛЬНО выполняй шаги по порядку):
Когда студент просит объяснить тему, понятие или задаёт учебный вопрос — выполни ВСЕ шаги:
1. Проверь историю диалога — есть ли уже информация о предпочтениях студента.
2. Если в истории НЕТ предпочтений — вызови get_student_preferences.
3. Вызови search_course_materials для поиска информации по теме.
4. Сформируй ответ на основе найденных материалов, адаптируя стиль под предпочтения.
5. Если предпочтения не были найдены ни в истории, ни через get_student_preferences — после ответа спроси студента, как ему удобнее получать объяснения, и сохрани через update_student_preferences.

Скилл «Разбор теста или экзамена»:
- Сначала вызови get_my_test_results или get_my_exam_results чтобы найти нужный ID.
- Затем вызови get_test_mistakes или get_exam_details чтобы получить детали.
- В конце сообщения добавь: «Задай вопрос по теме которую хочешь разобрать — я найду объяснение в материалах курса.»

Скилл «Помощь с лабораторной работой»:
- Сначала вызови get_course_labs чтобы увидеть список лаб и их задания.
- Определи нужную лабу и вызови search_course_materials с её названием и заданием.
- Предложи структуру выполнения и ключевые концепции — помоги студенту понять, но не решай за него.
- Если студент просит выполнить задание за него — ответь: «Это задание нужно выполнить самостоятельно. Задай конкретный вопрос по концепции и я объясню.»\
"""


def _log_agent_trace(messages: list, history_len: int) -> None:
    step = 0
    for msg in messages[history_len:]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                args_preview = str(tc.get("args", {}))[:120]
                logger.debug(f"  [шаг {step}] LLM → вызов инструмента: {tc['name']}({args_preview})")
                step += 1
        elif isinstance(msg, ToolMessage):
            content_preview = str(msg.content)[:500]
            logger.debug(f"  [шаг {step}] Инструмент '{msg.name}' → результат ({len(str(msg.content))} символов):\n{content_preview}")
            step += 1
        elif isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content
            content_type = type(content).__name__
            content_len = len(content) if isinstance(content, str) else len(str(content))
            logger.debug(f"  [шаг {step}] LLM → финальный ответ ({content_len} символов, тип={content_type}): {str(content)[:300]}")
            step += 1


TOOL_TITLES = {
    "search_course_materials": "Поиск по материалам курса",
    "get_my_test_results": "Результаты тестов",
    "get_test_mistakes": "Ошибки в тесте",
    "get_my_exam_results": "Результаты экзаменов",
    "get_exam_details": "Разбор экзамена",
    "get_my_progress": "Прогресс по курсу",
    "get_course_labs": "Лабораторные работы",
    "get_student_preferences": "Предпочтения студента",
    "update_student_preferences": "Сохранение предпочтений",
}


def ask(storage_id: str, question: str, history: list, student_id: int, course_id: int,
        chat_id: int) -> dict:
    """Ответ RAG-агента. Возвращает текст ответа, использованные инструменты и источники."""
    try:
        first, last = StudentRepository().get_first_and_last_names(student_id)
        student_name = f"{first} {last}"
    except Exception:
        student_name = "студент"
    try:
        info = CourseRepository().get_course_info(course_id)
        course_title = info[0][1] if info else "курс"
    except Exception:
        course_title = "курс"

    sources: list[str] = []
    tools = make_agent_tools(student_id, course_id, storage_id, chat_id, sources)
    agent = create_react_agent(get_chat_model(), tools)
    system_prompt = _build_system_prompt(student_name, course_title)
    messages = [SystemMessage(content=system_prompt)] + list(history) + [HumanMessage(content=question)]

    logger.info(f"▶ Agent | student={student_id} course={course_id} | '{question[:80]}'")
    result = agent.invoke({"messages": messages}, config={"recursion_limit": 16})
    _log_agent_trace(result["messages"], len(messages))

    tools_used: list[str] = []
    for msg in result["messages"][len(messages):]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                title = TOOL_TITLES.get(tc["name"], tc["name"])
                if title not in tools_used:
                    tools_used.append(title)

    content = _content_to_text(result["messages"][-1].content).strip()
    if not content:
        content = "Не удалось сформировать ответ. Попробуйте переформулировать вопрос."
    return {"response": content, "tools": tools_used, "sources": sources}
