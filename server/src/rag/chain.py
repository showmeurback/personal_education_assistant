import warnings
warnings.filterwarnings("ignore", message=".*create_react_agent.*")
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent

from llm.chat import _content_to_text, get_chat_model
from rag.tools import make_agent_tools
from database.sql.repositories.students import StudentRepository
from database.sql.repositories.courses import CourseRepository


def _build_system_prompt(student_name: str, course_title: str, preferences: str = "") -> str:
    return f"""\
Ты — AI-ассистент образовательной платформы по курсу «{course_title}».
Студент: {student_name}.

Правила поведения:
- Всегда отвечай на русском языке.
- Используй Markdown: заголовки, списки, таблицы, **жирный** для ключевых терминов.
- Формулы пиши обычным текстом (например, v = s / t, x^2 + 1, O(n log n)), без LaTeX.
- Будь дружелюбен и поддерживай студента.
- Если для ответа нужны данные — вызывай инструменты сразу, не объясняя что собираешься делать.
- НЕ придумывай ответы из головы — опирайся на материалы курса.
- Если в материалах курса информации по теме нет совсем — честно сообщи: «К сожалению, в материалах курса информации по этой теме не найдено.»
- Если студент явно просит изменить стиль объяснения или отвечает, как ему удобнее, — вызови update_student_preferences, чтобы сохранить стиль именно для этого чата. В остальных случаях этот инструмент не вызывай.

Скилл «Объяснение темы или понятия» (ОБЯЗАТЕЛЬНО выполняй шаги по порядку):
Когда студент просит объяснить тему, понятие или задаёт учебный вопрос — выполни ВСЕ шаги:
1. Сразу вызови search_course_materials для поиска информации по теме.
2. Сформируй ответ на основе найденных материалов, адаптируя стиль под предпочтения студента (они указаны ниже).
3. Если предпочтения не указаны и в истории диалога их тоже нет — в конце ответа одним предложением спроси, как студенту удобнее получать объяснения.

Скилл «Разбор теста или экзамена»:
- Сначала вызови get_my_test_results или get_my_exam_results чтобы найти нужный ID.
- Затем вызови get_test_mistakes или get_exam_details чтобы получить детали.
- В конце сообщения добавь: «Задай вопрос по теме которую хочешь разобрать — я найду объяснение в материалах курса.»

Скилл «Помощь с лабораторной работой»:
- Сначала вызови get_course_labs чтобы увидеть список лаб и их задания.
- Определи нужную лабу и вызови search_course_materials с её названием и заданием.
- Предложи структуру выполнения и ключевые концепции — помоги студенту понять, но не решай за него.
- Если студент просит выполнить задание за него — ответь: «Это задание нужно выполнить самостоятельно. Задай конкретный вопрос по концепции и я объясню.»

Предпочтения студента по объяснениям: {preferences or "не указаны"}.\
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


TOOL_STEPS = {
    "search_course_materials": "Ищу в материалах курса",
    "get_my_test_results": "Смотрю результаты твоих тестов",
    "get_test_mistakes": "Разбираю ошибки в тесте",
    "get_my_exam_results": "Смотрю результаты экзаменов",
    "get_exam_details": "Разбираю ответы экзамена",
    "get_my_progress": "Смотрю прогресс по курсу",
    "get_course_labs": "Смотрю лабораторные работы курса",
    "update_student_preferences": "Запоминаю, как тебе удобнее объяснять",
}


def _preferences_text(student_id: int, chat_id: int) -> str:
    """Предпочтения чата, иначе — профиля студента; подставляются прямо в задание агента,
    поэтому отдельный вызов инструмента (и лишнее обращение к модели) не нужен."""
    from database.sql.repositories.chat_preferences import ChatPreferencesRepository
    from database.sql.repositories.student_preferences import StudentPreferencesRepository
    try:
        prefs = ChatPreferencesRepository().get_preferences(chat_id) or \
            StudentPreferencesRepository().get_preferences(student_id)
    except Exception:
        prefs = None
    if not prefs:
        return ""
    style = prefs.get("preferred_explanation_style") or "не указан"
    notes = prefs.get("notes") or ""
    return f"стиль — {style}" + (f"; заметки — {notes}" if notes else "")


def _prepare(storage_id: str, question: str, history: list, student_id: int, course_id: int, chat_id: int):
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
    tools = [t for t in make_agent_tools(student_id, course_id, storage_id, chat_id, sources)
             if t.name != "get_student_preferences"]
    agent = create_react_agent(get_chat_model(), tools)
    system_prompt = _build_system_prompt(student_name, course_title, _preferences_text(student_id, chat_id))
    messages = [SystemMessage(content=system_prompt)] + list(history) + [HumanMessage(content=question)]
    return agent, messages, sources


def _tools_used(new_messages: list) -> list[str]:
    used: list[str] = []
    for msg in new_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                title = TOOL_TITLES.get(tc["name"], tc["name"])
                if title not in used:
                    used.append(title)
    return used


def _final_text(msg) -> str:
    content = _content_to_text(getattr(msg, "content", "")).strip()
    return content or "Не удалось сформировать ответ. Попробуйте переформулировать вопрос."


def ask(storage_id: str, question: str, history: list, student_id: int, course_id: int,
        chat_id: int) -> dict:
    """Ответ RAG-агента. Возвращает текст ответа, использованные инструменты и источники."""
    agent, messages, sources = _prepare(storage_id, question, history, student_id, course_id, chat_id)
    logger.info(f"▶ Agent | student={student_id} course={course_id} | '{question[:80]}'")
    result = agent.invoke({"messages": messages}, config={"recursion_limit": 16})
    _log_agent_trace(result["messages"], len(messages))
    new = result["messages"][len(messages):]
    return {"response": _final_text(result["messages"][-1]), "tools": _tools_used(new), "sources": sources}


def stream_ask(storage_id: str, question: str, history: list, student_id: int, course_id: int,
               chat_id: int):
    """Потоковый ответ RAG-агента: события по мере работы.

    {"type": "step", "text": …}   — агент вызывает инструмент или формулирует ответ;
    {"type": "token", "text": …}  — очередной фрагмент текста ответа;
    {"type": "reset"}             — модель написала текст, но затем решила вызвать инструмент:
                                    показанный черновик нужно убрать;
    {"type": "done", "response": …, "tools": […], "sources": […]} — итог (полный текст ответа).
    """
    agent, messages, sources = _prepare(storage_id, question, history, student_id, course_id, chat_id)
    logger.info(f"▶ Agent (поток) | student={student_id} course={course_id} | '{question[:80]}'")
    yield {"type": "step", "text": "Разбираю вопрос"}
    new_messages: list = []
    streamed = False  # в текущем обращении к модели уже показан текст
    for mode, data in agent.stream({"messages": messages}, config={"recursion_limit": 16},
                                   stream_mode=["messages", "updates"]):
        if mode == "messages":
            chunk, meta = data
            if meta.get("langgraph_node") != "agent" or getattr(chunk, "tool_call_chunks", None):
                continue
            text = _content_to_text(getattr(chunk, "content", ""))
            if text:
                streamed = True
                yield {"type": "token", "text": text}
            continue
        for node, update in (data or {}).items():  # mode == "updates": узел графа завершён
            msgs = (update or {}).get("messages", [])
            new_messages.extend(msgs)
            if node == "tools":
                yield {"type": "step", "text": "Формулирую ответ"}
                continue
            for msg in msgs:
                if node == "agent" and isinstance(msg, AIMessage) and msg.tool_calls:
                    if streamed:
                        yield {"type": "reset"}
                    streamed = False
                    for tc in msg.tool_calls:
                        step = TOOL_STEPS.get(tc["name"], TOOL_TITLES.get(tc["name"], tc["name"]))
                        query = (tc.get("args") or {}).get("query")
                        yield {"type": "step", "text": f"{step}: «{query}»" if query else step}
    _log_agent_trace(messages + new_messages, len(messages))
    final = next((m for m in reversed(new_messages) if isinstance(m, AIMessage) and not m.tool_calls), None)
    yield {"type": "done", "response": _final_text(final), "tools": _tools_used(new_messages),
           "sources": sources}
