from typing import List
from .models import Question, EvaluationResponse, EvaluationResult
from .config import Config


class TestEvaluator:

    @staticmethod
    def evaluate_answers(questions: List[Question], user_answers: List[str]) -> EvaluationResponse:
        try:
            if len(questions) != len(user_answers):
                return EvaluationResponse(
                    success=False,
                    total_questions=len(questions),
                    correct_answers=0,
                    wrong_answers=0,
                    percentage=0.0,
                    grade="0",
                    grade_description="Ошибка: количество ответов не совпадает",
                    error="Кол-во ответов не совпадает"
                )

            correct_count = 0
            results = []

            for i, (question, user_answer) in enumerate(zip(questions, user_answers)):
                correct_answer = question.correct_answer
                is_correct = (user_answer or "").strip().upper() == correct_answer.strip().upper()

                if is_correct:
                    correct_count += 1

                result = EvaluationResult(
                    question_num=question.question_num,
                    question_text=question.text,
                    user_answer=(user_answer or "").strip().upper(),
                    correct_answer=correct_answer,
                    is_correct=is_correct,
                    options=question.options
                )

                results.append(result)

            total = len(questions)
            wrong_count = total - correct_count
            percentage = (correct_count / total * 100) if total > 0 else 0

            grade, description = TestEvaluator._get_grade(percentage)

            return EvaluationResponse(
                success=True,
                total_questions=total,
                correct_answers=correct_count,
                wrong_answers=wrong_count,
                percentage=round(percentage, 2),
                grade=grade,
                grade_description=description,
                results=results
            )

        except Exception as e:
            return EvaluationResponse(
                success=False,
                total_questions=len(questions),
                correct_answers=0,
                wrong_answers=0,
                percentage=0.0,
                grade="0",
                grade_description="Ошибка оценки",
                error=str(e)
            )

    @staticmethod
    def _get_grade(percentage: float) -> tuple[str, str]:
        """Оценка по 10-балльной шкале: первая граница, не превышающая процент."""
        for lower, grade, description in Config.GRADE_SCALE:
            if percentage >= lower:
                return grade, description
        return "0", "Неудовлетворительно"
