from agents.test_generator.evaluator import TestEvaluator
from agents.test_generator.models import Question
from agents.test_generator.parser import TestParser


def q(n, correct="A"):
    return Question(question_num=n, text=f"Вопрос {n}?", options={"A": "1", "B": "2", "C": "3", "D": "4"},
                    correct_answer=correct)


def test_grade_scale_has_no_gaps():
    # 5 из 6 = 83.33 % — раньше попадало в «дыру» между интервалами и давало 0
    assert TestEvaluator._get_grade(83.33)[0] == "7"
    assert TestEvaluator._get_grade(71.43)[0] == "5"
    assert TestEvaluator._get_grade(95.5)[0] == "9"
    assert TestEvaluator._get_grade(100)[0] == "10"
    assert TestEvaluator._get_grade(0)[0] == "0"


def test_evaluation_is_deterministic():
    questions = [q(i) for i in range(1, 7)]
    res = TestEvaluator.evaluate_answers(questions, ["A", "a ", "A", "A", "A", "B"])
    assert res.correct_answers == 5 and res.percentage == 83.33 and res.grade == "7"


def test_parser_ignores_word_question_inside_text():
    text = ("ВОПРОС 1: Какой вопрос решает быстрая сортировка?\nA) Упорядочивание\nB) Поиск\n"
            "C) Хеширование\nD) Шифрование\nОТВЕТ: A\n\n**ВОПРОС 2:** Сложность пузырька?\n"
            "A. O(n)\nB. O(n^2)\nC. O(log n)\nD. O(1)\nОТВЕТ: B")
    questions, errors = TestParser().parse_questions(text)
    assert [x.correct_answer for x in questions] == ["A", "B"] and not errors
    assert questions[1].text == "Сложность пузырька?"


def test_parser_rejects_question_without_options():
    questions, errors = TestParser().parse_questions("ВОПРОС 1: Что такое O-нотация?\nОТВЕТ: A")
    assert not questions and errors
