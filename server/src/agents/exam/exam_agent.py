from __future__ import annotations

from database.sql import CourseRepository
from llm.chat import invoke_text
from llm.json_utils import extract_json
from models.exam import ExamQuestion, ExamResult, ExamSession
from .parser import parse_question_payload
from .prompts import ANSWER_EVALUATION_PROMPT, QUESTION_GENERATION_PROMPT

VERDICTS = ("correct", "partial", "incorrect")


def _verdict_from_score(score: int) -> str:
    return "correct" if score >= 75 else "partial" if score >= 35 else "incorrect"


class ExamAgent:
    """Агент пробного экзамена: готовит вопросы и оценивает ответы студента."""

    def create_session(self, *, course_id: int, question_count: int = 3, language: str = "ru") -> ExamSession:
        context = CourseRepository().get_exam_questions(course_id)
        if not context or not context.strip():
            raise ValueError("Преподаватель не задал экзаменационные вопросы для этого курса.")
        questions = self._prepare_questions(context=context, desired_count=question_count, language=language)
        if not questions:
            raise ValueError("Не удалось подготовить вопросы из материалов курса.")
        return ExamSession(agent=self, questions=questions, context=context, language=language)

    def evaluate_answer(self, *, question: ExamQuestion, answer: str, context: str, language: str) -> ExamResult:
        prompt = ANSWER_EVALUATION_PROMPT.format(
            language=language, context=context[:6000], question=question.text,
            reference_answer=question.reference_answer or "(не задан)", student_answer=answer,
        )
        raw = invoke_text(prompt, temperature=0.0, max_tokens=1024)
        data = extract_json(raw)
        if not isinstance(data, dict):
            return ExamResult(question=question, user_answer=answer, verdict="incorrect",
                              recommendation="Не удалось автоматически оценить ответ, попробуйте ещё раз.",
                              issues=["Ответ модели не распознан"], score=None, raw_feedback=raw)
        try:
            score = int(round(float(data.get("score"))))
            score = max(0, min(100, score))
        except (TypeError, ValueError):
            score = None
        verdict = str(data.get("verdict", "")).lower().strip()
        # символьная проверка согласованности: категория должна соответствовать баллу
        if score is not None and (verdict not in VERDICTS or verdict != _verdict_from_score(score)):
            verdict = _verdict_from_score(score)
        if verdict not in VERDICTS:
            verdict = "incorrect"
        issues = [str(i) for i in (data.get("issues") or []) if str(i).strip()][:6]
        return ExamResult(
            question=question, user_answer=answer, verdict=verdict,
            recommendation=str(data.get("recommendation") or "Повторите материал по теме вопроса."),
            issues=issues, score=str(score) if score is not None else None,
            raw_feedback=str(data.get("summary") or ""),
        )

    def _prepare_questions(self, *, context: str, desired_count: int, language: str) -> list[ExamQuestion]:
        # вопросами преподавателя считаются только элементы, оформленные как вопрос;
        # описательный текст («вопросы охватывают: …») используется как материал для генерации
        parsed = [q for q in parse_question_payload(context) if "?" in q.text]
        if len(parsed) >= desired_count:
            # вопросы преподавателя используются напрямую, без генерации
            return parsed[:desired_count]
        prompt = QUESTION_GENERATION_PROMPT.format(question_count=desired_count, language=language) \
            + "\n\n" + context[:8000]
        generated = parse_question_payload(invoke_text(prompt, temperature=0.4))
        combined = parsed + [q for q in generated if q.text not in {p.text for p in parsed}]
        for i, q in enumerate(combined, start=1):
            q.id = i
        return combined[:desired_count]
