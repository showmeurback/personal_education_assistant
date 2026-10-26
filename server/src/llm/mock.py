"""Детерминированная заглушка языковой модели.

Используется в автоматических тестах и при демонстрации без доступа к API.
Ответ формируется по маркеру задачи в системном сообщении:
  [TASK:JUDGE]     — вердикт оценщика отчёта (JSON);
  [TASK:FEEDBACK]  — пояснение для студента;
  [TASK:EXAM_EVAL] — оценка ответа на экзаменационный вопрос (JSON);
  [TASK:EXAM_GEN]  — генерация экзаменационных вопросов (JSON);
  [TASK:TEST_GEN]  — генерация тестовых вопросов (текстовый формат);
  [TASK:IMAGE]     — описание изображения отчёта.
Решение оценщика принимается по доле ключевых слов задания, встречающихся
в отчёте, — этого достаточно для проверки логики конвейера, но не качества.
"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_WORD = re.compile(r"[a-zа-яё]{5,}", re.IGNORECASE)


def _words(text: str) -> set[str]:
    return {w.lower()[:6] for w in _WORD.findall(text or "")}


def _section(text: str, start: str, end: str | None = None) -> str:
    i = text.find(start)
    if i < 0:
        return ""
    i += len(start)
    j = text.find(end, i) if end else -1
    return text[i:j] if j >= 0 else text[i:]


class MockChatModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "mock"

    def bind_tools(self, tools: Any, **kwargs: Any):  # агенту инструменты не нужны
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        full = "\n".join(m.content if isinstance(m.content, str) else
                         " ".join(str(p.get("text", "")) for p in m.content if isinstance(p, dict))
                         for m in messages)
        text = self._answer(full)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    @staticmethod
    def _answer(full: str) -> str:
        if "[TASK:JUDGE]" in full:
            task = _section(full, "<requirements>", "</requirements>")
            report = _section(full, "<report>", "</report>")
            task_w, rep_w = _words(task), _words(report)
            coverage = len(task_w & rep_w) / max(1, len(task_w))
            strict = "[STANCE:STRICT]" in full
            loyal = "[STANCE:LOYAL]" in full
            threshold = 0.5 if strict else 0.25 if loyal else 0.35
            verdict = coverage >= threshold
            confidence = round(min(0.95, 0.55 + abs(coverage - threshold)), 2)
            return json.dumps({
                "verdict": verdict,
                "confidence": confidence,
                "criteria": [{"name": "Соответствие заданию", "met": verdict,
                              "comment": f"Покрытие ключевых понятий задания: {coverage:.0%}"}],
                "summary": "Отчёт соответствует заданию" if verdict else "Отчёт не раскрывает задание",
            }, ensure_ascii=False)
        if "[TASK:TEST_REVIEW]" in full:
            nums = re.findall(r"Вопрос (\d+):", full)
            return json.dumps([{"question_num": int(n), "explanation": "В материале курса указан правильный вариант "
                                "(объяснение заглушки)."} for n in nums], ensure_ascii=False)
        if "[TASK:WEAK_TOPICS]" in full:
            topics = re.findall(r"^Тема: (.+)$", full, re.MULTILINE)
            return json.dumps([{"topic": t, "advice": "Повторите материал по теме и пройдите тест ещё раз "
                                "(совет заглушки)."} for t in topics], ensure_ascii=False)
        if "[TASK:IMAGE]" in full:
            return "Скриншот окна программы с результатами выполнения (описание заглушки)."
        if "[TASK:FEEDBACK]" in full:
            return ("Отчёт не принят: в нём не раскрыты ключевые требования задания. "
                    "Опишите цель работы, ход выполнения и полученные результаты.")
        if "[TASK:EXAM_EVAL]" in full:
            answer = _section(full, "<answer>", "</answer>").strip()
            score = 80 if len(answer.split()) >= 15 else 40 if answer else 0
            verdict = "correct" if score >= 70 else "partial" if score > 0 else "incorrect"
            return json.dumps({"verdict": verdict, "score": score,
                               "summary": "Ответ оценён заглушкой", "issues": [],
                               "recommendation": "Раскройте понятие подробнее."}, ensure_ascii=False)
        if "[TASK:EXAM_GEN]" in full:
            return json.dumps([{"question": f"Вопрос {i} по материалам курса",
                                "reference_answer": "Эталон"} for i in range(1, 4)], ensure_ascii=False)
        if "[TASK:TEST_GEN]" in full:
            n = int(_section(full, "<count>", "</count>") or 3)
            blocks = [f"ВОПРОС {i}: Тестовый вопрос {i}?\nA) Вариант 1\nB) Вариант 2\nC) Вариант 3\nD) Вариант 4\nОТВЕТ: A"
                      for i in range(1, n + 1)]
            return "\n\n".join(blocks)
        return "Ответ заглушки языковой модели."
