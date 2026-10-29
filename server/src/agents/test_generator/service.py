"""Генерация и проверка тестов.

Нейросетевой компонент (LLM) генерирует вопросы по фрагментам материалов курса,
найденным гибридным поиском; символьный компонент разбирает ответ модели по
формальной грамматике (ВОПРОС / A–D / ОТВЕТ), отбраковывает некорректные
вопросы и детерминированно оценивает ответы студента по шкале.

Каждый сгенерированный тест хранится под собственным идентификатором и
привязан к студенту. Прежняя реализация держала один общий «сеанс» на всё
приложение, поэтому тест одного студента перезаписывал тест другого.
"""
from __future__ import annotations

import random
import re
import threading
import time
import uuid
from dataclasses import dataclass, field

from common.text_extraction import normalize_whitespace
from database.sql.repositories.test_results import TestResultRepository
from .agent import TestGenerationAgent
from .config import Config
from .evaluator import TestEvaluator
from .material_provider import MaterialProvider
from .models import Question
from .review import review_mistakes

_TTL_SECONDS = 3 * 3600
_MAX_SESSIONS = 2000


@dataclass
class TestSession:
    student_id: int
    course_id: int
    topic: str | None
    source: str
    difficulty: str
    questions: list[Question]
    material: str | None = None  # фрагменты материалов, по которым сгенерирован тест (для разбора ошибок)
    created_at: float = field(default_factory=time.time)
    submitted: bool = False


class TestServiceError(Exception):
    pass


# Вариант, который ссылается на другие варианты («все перечисленные», «A и B»), нельзя переставлять
_POSITIONAL = re.compile(r"(все|ни один|оба)\b.*(вариант|перечисл|ответ)|\b[A-DА-Г]\s*(и|или|,)\s*[A-DА-Г]\b",
                         re.IGNORECASE)


def shuffle_options(q: Question, rng: random.Random) -> Question:
    """Символьная перестановка вариантов ответа.

    Языковые модели чаще ставят верный ответ на одну и ту же позицию (на практике — «B»),
    и студент мог бы угадывать по букве. Варианты переставляются случайно, буква верного
    ответа пересчитывается; вопросы с вариантами, ссылающимися на другие варианты, не трогаются."""
    letters = sorted(q.options)
    if q.correct_answer not in q.options or any(_POSITIONAL.search(t) for t in q.options.values()):
        return q
    order = letters[:]
    rng.shuffle(order)
    options = {new: q.options[old] for new, old in zip(letters, order)}
    correct = letters[order.index(q.correct_answer)]
    return q.model_copy(update={"options": options, "correct_answer": correct})


class TestService:
    def __init__(self) -> None:
        self._sessions: dict[str, TestSession] = {}
        self._lock = threading.Lock()
        self.agent = TestGenerationAgent()
        self.material_provider = MaterialProvider()

    def _put(self, session: TestSession) -> str:
        test_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            for key in [k for k, s in self._sessions.items() if now - s.created_at > _TTL_SECONDS]:
                del self._sessions[key]
            if len(self._sessions) >= _MAX_SESSIONS:
                oldest = min(self._sessions, key=lambda k: self._sessions[k].created_at)
                del self._sessions[oldest]
            self._sessions[test_id] = session
        return test_id

    def get(self, test_id: str, student_id: int) -> TestSession:
        session = self._sessions.get(test_id)
        if session is None or session.student_id != student_id:
            raise TestServiceError("Тест не найден или срок его действия истёк. Сгенерируйте новый тест.")
        return session

    def _generate(self, *, student_id: int, course_id: int, material: str, num_questions: int,
                  difficulty: str, topic: str | None, source: str) -> dict:
        material = normalize_whitespace(material)[:Config.MAX_MATERIAL_LENGTH]
        response = self.agent.generate_from_file(material=material, num_questions=num_questions,
                                                 difficulty=difficulty)
        if not response.success or not response.questions:
            raise TestServiceError(response.error or "Не удалось сгенерировать тест")
        rng = random.Random()
        questions = [shuffle_options(q, rng) for q in response.questions[:num_questions]]
        for i, q in enumerate(questions, start=1):
            q.question_num = i
        test_id = self._put(TestSession(student_id=student_id, course_id=course_id, topic=topic,
                                        source=source, difficulty=difficulty, questions=questions,
                                        material=material))
        return {
            "test_id": test_id,
            "difficulty": difficulty,
            "total_questions": len(questions),
            "questions": [{"question_num": q.question_num, "text": q.text, "options": q.options,
                           "type": q.type} for q in questions],
        }

    def generate_by_topic(self, *, student_id: int, course_id: int, topic: str, num_questions: int,
                          difficulty: str) -> dict:
        ok, material, message = self.material_provider.get_validated_material(topic, course_id=course_id)
        if not ok or not material:
            raise TestServiceError(message)
        return self._generate(student_id=student_id, course_id=course_id, material=material,
                              num_questions=num_questions, difficulty=difficulty,
                              topic=topic.strip(), source="topic")

    def generate_by_material(self, *, student_id: int, course_id: int, material: str, filename: str,
                             num_questions: int, difficulty: str) -> dict:
        if len(material.strip()) < 200:
            raise TestServiceError("В файле слишком мало текста для генерации теста")
        return self._generate(student_id=student_id, course_id=course_id, material=material,
                              num_questions=num_questions, difficulty=difficulty,
                              topic=f"Файл: {filename}", source="file")

    def submit(self, *, test_id: str, student_id: int, answers: list[str]) -> dict:
        session = self.get(test_id, student_id)
        if session.submitted:
            raise TestServiceError("Ответы на этот тест уже отправлены")
        if len(answers) != len(session.questions):
            raise TestServiceError(f"Ожидается {len(session.questions)} ответов, получено {len(answers)}")
        result = TestEvaluator.evaluate_answers(session.questions, answers)
        if not result.success:
            raise TestServiceError(result.error or "Ошибка оценки")
        session.submitted = True
        wrong = [{"question_num": r.question_num, "question_text": r.question_text, "options": r.options,
                  "user_answer": r.user_answer, "correct_answer": r.correct_answer}
                 for r in (result.results or []) if not r.is_correct]
        explanations = review_mistakes(wrong, session.material)
        TestResultRepository().save(
            student_id=student_id, course_id=session.course_id, topic=session.topic,
            source=session.source, difficulty=session.difficulty,
            total_questions=result.total_questions, correct_answers=result.correct_answers,
            wrong_answers=result.wrong_answers, percentage=result.percentage,
            answers=[{
                "question_num": r.question_num, "question_text": r.question_text, "options": r.options,
                "user_answer": r.user_answer, "correct_answer": r.correct_answer,
                "is_correct": r.is_correct, "explanation": explanations.get(r.question_num),
            } for r in (result.results or [])],
        )
        return {
            "total_questions": result.total_questions,
            "correct_answers": result.correct_answers,
            "wrong_answers": result.wrong_answers,
            "percentage": result.percentage,
            "grade": result.grade,
            "grade_description": result.grade_description,
            "results": [{**r.model_dump(), "explanation": explanations.get(r.question_num)}
                        for r in (result.results or [])],
        }
