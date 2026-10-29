"""Карта пробелов (символьная часть) и разбор ошибок теста (заглушка модели)."""
from agents.progress import weak_topics as wt
from agents.progress.weak_topics import Evidence, mastery_of, rank_topics
from agents.test_generator.review import review_mistakes


def ev(source, title, m, created, details=None):
    return Evidence(source, title, m, created, details or [])


def test_recent_results_weigh_more():
    # от новых к старым: недавний провал важнее давнего успеха
    assert mastery_of([ev("test", "x", 0.2, "2"), ev("test", "x", 1.0, "1")]) < 0.6
    assert mastery_of([ev("test", "x", 1.0, "2"), ev("test", "x", 0.2, "1")]) > 0.6


def test_same_topic_is_merged_and_weak_topics_ranked(monkeypatch):
    monkeypatch.setattr(wt, "_lemma_key", lambda t: frozenset(t.lower().replace(",", "").split()))
    items = [
        ev("test", "быстрая сортировка", 0.4, "2026-10-02", ["Тест: ошибка в вопросе «опорный элемент»"]),
        ev("test", "Быстрая сортировка", 0.5, "2026-10-01"),
        ev("exam", "сложность сортировки пузырьком", 0.9, "2026-10-03"),
        ev("lab", "ЛР 2. Хеш-таблицы", 0.3, "2026-10-04", ["Отчёт: нет анализа коллизий"]),
        ev("test", "деревья поиска", 0.95, "2026-10-05"),
    ]
    weak, strong = rank_topics(items)
    assert [t.topic for t in weak] == ["ЛР 2. Хеш-таблицы", "быстрая сортировка"]
    assert weak[1].evidence["test"] == 2 and weak[1].details
    assert {t.topic for t in strong} == {"сложность сортировки пузырьком", "деревья поиска"}


def test_advice_from_mock_model_is_attached(monkeypatch):
    monkeypatch.setattr(wt, "_lemma_key", lambda t: frozenset(t.split()))
    weak, _ = rank_topics([ev("test", "графы", 0.3, "1", ["Тест: ошибка"])])
    assert wt.advise(weak, "Алгоритмы") and "заглушки" in weak[0].advice


def test_mistake_review_explains_each_wrong_answer():
    wrong = [{"question_num": 2, "question_text": "Сложность быстрой сортировки?", "options": {"A": "O(n)", "B": "O(n log n)"},
              "user_answer": "A", "correct_answer": "B"},
             {"question_num": 5, "question_text": "Что такое опорный элемент?", "options": {"A": "…", "B": "…"},
              "user_answer": "", "correct_answer": "A"}]
    out = review_mistakes(wrong, "Быстрая сортировка имеет среднюю сложность O(n log n).")
    assert set(out) == {2, 5} and all(out.values())
    assert review_mistakes([], "x") == {}


def test_assistant_test_mistakes_tool_reads_explanations(monkeypatch):
    """Инструмент ассистента «Ошибки в тесте» принимает строки с объяснением (7 полей) и без него (6)."""
    from rag import queries

    class Repo:
        def get_owner(self, _rid):
            return (7,)

        def get_answers(self, _rid):
            return [(1, "Вопрос 1", '{"A": "a", "B": "b"}', "B", "A", False, "Верный ответ — A"),
                    (2, "Вопрос 2", {"A": "a"}, "A", "A", True, None),
                    (3, "Вопрос 3", {"A": "a", "B": "b"}, "A", "B", False)]

    monkeypatch.setattr(queries, "TestResultRepository", Repo)
    mistakes = queries.query_test_mistakes(1, student_id=7)
    assert [m["question_num"] for m in mistakes] == [1, 3]
    assert mistakes[0]["explanation"] == "Верный ответ — A" and "explanation" not in mistakes[1]


def test_generated_options_are_shuffled_without_breaking_answers():
    """Верный ответ не остаётся всегда на позиции «B»; текст верного ответа сохраняется."""
    import random
    from agents.test_generator.models import Question
    from agents.test_generator.service import shuffle_options
    rng = random.Random(7)
    positions = set()
    for i in range(40):
        q = Question(question_num=i, text="Вопрос?", correct_answer="B",
                     options={"A": "неверно 1", "B": "верно", "C": "неверно 2", "D": "неверно 3"})
        s = shuffle_options(q, rng)
        assert s.options[s.correct_answer] == "верно" and sorted(s.options) == ["A", "B", "C", "D"]
        assert sorted(s.options.values()) == sorted(q.options.values())
        positions.add(s.correct_answer)
    assert positions == {"A", "B", "C", "D"}
    keep = Question(question_num=1, text="?", correct_answer="D",
                    options={"A": "1", "B": "2", "C": "3", "D": "Все перечисленные варианты"})
    assert shuffle_options(keep, rng) == keep
