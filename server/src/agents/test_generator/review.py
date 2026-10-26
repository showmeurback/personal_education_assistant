"""Разбор ошибок теста (нейросетевой агент).

Символьный оценщик уже определил, какие ответы неверны; агент получает только эти
вопросы вместе с фрагментами материалов курса, по которым тест был сгенерирован, и
объясняет каждую ошибку в 1–3 предложениях: почему верен эталонный вариант и где
это сказано в материалах. Оценка теста от разбора не зависит; при сбое модели
студент получает результат без объяснений.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from llm.chat import invoke_text, split_model
from llm.json_utils import extract_json
from log import logger
from settings import llm_settings

REVIEW_SYSTEM = """[TASK:TEST_REVIEW]
Ты — преподаватель. Студент ошибся в вопросах теста. Для каждого вопроса объясни
по-русски в 1–3 предложениях, почему верен правильный вариант и в чём ошибка
выбранного, опираясь только на материал курса из <material>. Если в материале есть
подходящее место, укажи его кратко («в материале сказано, что …»). Не выдумывай фактов.
Ответь СТРОГО JSON-массивом без пояснений вне JSON:
[{"question_num": номер, "explanation": "объяснение"}]"""

MAX_MATERIAL_CHARS = 12000


def review_mistakes(wrong: list[dict], material: str | None) -> dict[int, str]:
    """wrong: [{question_num, question_text, options, user_answer, correct_answer}] → {номер: объяснение}."""
    if not wrong:
        return {}
    lines = []
    for w in wrong:
        opts = "; ".join(f"{k}) {v}" for k, v in (w.get("options") or {}).items())
        lines.append(f"Вопрос {w['question_num']}: {w['question_text']}\nВарианты: {opts}\n"
                     f"Ответ студента: {w['user_answer'] or '—'}; правильный ответ: {w['correct_answer']}")
    messages = [SystemMessage(content=REVIEW_SYSTEM),
                HumanMessage(content=f"<material>\n{(material or 'не указан')[:MAX_MATERIAL_CHARS]}\n</material>\n\n"
                                     f"<mistakes>\n" + "\n\n".join(lines) + "\n</mistakes>")]
    try:
        name, thinking = split_model(llm_settings.feedback_model)
        raw = invoke_text(messages, temperature=0.2, max_tokens=300 * len(wrong) + 200,
                          model=name, thinking=thinking)
    except Exception as exc:  # объяснения необязательны: результат теста уже посчитан
        logger.warning(f"Разбор ошибок теста не получен: {type(exc).__name__}: {exc}")
        return {}
    data = extract_json(raw)
    if isinstance(data, dict):
        data = data.get("items") or data.get("mistakes") or [data]
    out: dict[int, str] = {}
    for item in data or []:
        if isinstance(item, dict):
            try:
                num = int(item.get("question_num"))
            except (TypeError, ValueError):
                continue
            text = " ".join(str(item.get("explanation", "")).split())[:800]
            if text:
                out[num] = text
    return out
