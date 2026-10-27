"""Наполнение базы знаний демонстрационными данными.

Создаёт двух преподавателей, десять студентов, десять курсов с лекциями и
лабораторными работами, зачисления, заявки, результаты тестов и экзаменов,
отчёты, оценки курсов и диалоги с ассистентом. Пароль совпадает с логином:
teacher1/teacher1, student1/student1 и т. д.

Наполнение выполняется один раз: если преподаватель teacher1 уже есть, база
не изменяется (повторное наполнение — run(reset=True)). Лекции индексируются
в векторную базу отдельно (ensure_materials), потому что для этого нужен сервис
эмбеддингов: при его недоступности курсы создаются без материалов, а индексация
повторяется при следующем запуске.
"""
from __future__ import annotations

import json
import random
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2

from auth.security import hash_password
from log import logger
from settings import EducationDatabaseConfig, settings

from . import data as D
from .materials import EXAMS, LECTURES
from .questions import QUESTIONS

TEACHER_LOGINS = ("teacher1", "teacher2")
STUDENT_LOGINS = tuple(f"student{i}" for i in range(1, 11))
LAB_MIN_WORDS = 120
LAB_SECTIONS = "Цель\nВывод"
LECTURE_FILENAME = "Конспект лекций.txt"


def _connect():
    cfg = EducationDatabaseConfig()
    return psycopg2.connect(host=cfg.host, port=cfg.port, dbname=cfg.name, user=cfg.user, password=cfg.password)


def is_seeded() -> bool:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM teachers WHERE login = %s", (TEACHER_LOGINS[0],))
        return cur.fetchone() is not None


def _delete_demo(cur) -> None:
    cur.execute("SELECT id FROM students WHERE login = ANY(%s)", (list(STUDENT_LOGINS),))
    student_ids = [r[0] for r in cur.fetchall()]
    if student_ids:
        try:  # отпечатки удаляемых отчётов, иначе новые отчёты сравнивались бы с несуществующими
            from weaviate.classes.query import Filter

            from database.vector.client import wvt_client
            from database.vector.database import FINGERPRINT_COLLECTION

            @wvt_client
            def drop(client=None):
                client.collections.get(FINGERPRINT_COLLECTION).data.delete_many(
                    where=Filter.by_property("student_id").contains_any(student_ids))
            drop()
        except Exception as exc:
            logger.warning(f"Не удалось удалить отпечатки демонстрационных отчётов: {exc}")
    cur.execute("SELECT id, storage_id FROM courses WHERE teacher_id IN "
                "(SELECT id FROM teachers WHERE login = ANY(%s))", (list(TEACHER_LOGINS),))
    storages = [r[1] for r in cur.fetchall() if r[1]]
    cur.execute("DELETE FROM courses WHERE teacher_id IN (SELECT id FROM teachers WHERE login = ANY(%s))",
                (list(TEACHER_LOGINS),))
    cur.execute("DELETE FROM students WHERE login = ANY(%s)", (list(STUDENT_LOGINS),))
    cur.execute("DELETE FROM teachers WHERE login = ANY(%s)", (list(TEACHER_LOGINS),))
    if storages:
        try:
            from database.vector.repositories import StorageManager
            for sid in storages:
                StorageManager.delete_storage(sid)
        except Exception as exc:  # векторная база может быть недоступна — не критично
            logger.warning(f"Не удалось удалить материалы демонстрационных курсов: {exc}")


# ── тексты отчётов ───────────────────────────────────────────────────────────

_STEP_NOTES = ["Решение проверено на тестовых данных.", "Промежуточные результаты сохранены в репозитории.",
               "Возникшие ошибки исправлены, исправления описаны в комментариях к коду.",
               "Выполнение заняло около двух часов, основное время ушло на отладку.",
               "Корректность подтверждена запуском автоматических тестов."]
_RESULTS = ["Все пункты задания выполнены, результаты сведены в таблицу 1 и на рисунок 1.",
            "Результаты измерений приведены в таблице 1; расхождение повторных запусков не превышает 5 %.",
            "Полученные результаты совпали с ожидаемыми по материалам лекций.",
            "Большая часть пунктов выполнена полностью, ограничения решения описаны ниже."]


def _report_text(lab_number: int, lab_title: str, task: str, first: str, last: str, rng: random.Random) -> str:
    sentences = [s.strip() for s in task.replace("\n", " ").split(". ") if s.strip()]
    goal = sentences[0].rstrip(".")
    steps = "\n".join(f"{i}. {s.rstrip('.')}. {rng.choice(_STEP_NOTES)}" for i, s in enumerate(sentences, 1))
    return (f"Лабораторная работа №{lab_number}\n{lab_title}\nВыполнил(а): {first} {last}\n\n"
            f"Цель работы\nОсвоить на практике тему «{lab_title}»: {goal[0].lower() + goal[1:]}.\n\n"
            f"Задание\n{task}\n\n"
            f"Ход выполнения\n{steps}\n\n"
            f"Результаты\n{rng.choice(_RESULTS)} Исходный код и данные приложены к отчёту.\n\n"
            f"Вывод\nВ ходе лабораторной работы по теме «{lab_title}» выполнены все пункты задания, "
            f"закреплены теоретические положения лекций и получен практический опыт. "
            f"{rng.choice(['Наибольшую сложность вызвала отладка', 'Отдельное внимание уделено проверке результатов', 'Решение можно улучшить, расширив набор тестов'])}.\n")


# ── наполнение ───────────────────────────────────────────────────────────────

def run(reset: bool = False) -> bool:
    """Создаёт демонстрационные данные. Возвращает False, если они уже были."""
    rng = random.Random(2026)
    now = datetime.now().replace(microsecond=0)
    start = now - timedelta(days=60)

    def moment(day: float) -> datetime:
        return start + timedelta(days=day, minutes=rng.randint(0, 600))

    reports_dir = Path(settings.uploads_dir) / "reports"
    created_files: list[Path] = []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM teachers WHERE login = %s", (TEACHER_LOGINS[0],))
        if cur.fetchone():
            if not reset:
                return False
            _delete_demo(cur)

        ids: dict[str, int] = {}
        for key, (login, first, last) in zip(("t1", "t2"), [("teacher1", "Алексей", "Соколов"),
                                                            ("teacher2", "Марина", "Белова")]):
            cur.execute("INSERT INTO teachers (login, password, first_name, last_name) "
                        "VALUES (%s,%s,%s,%s) RETURNING id", (login, hash_password(login), first, last))
            ids[key] = cur.fetchone()[0]

        names = {}
        for i, (login, _pwd, first, last, characteristic) in enumerate(D.students_data, 1):
            cur.execute("INSERT INTO students (login, password, first_name, last_name, characteristic) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                        (login, hash_password(login), first, last, characteristic))
            ids[f"s{i}"] = cur.fetchone()[0]
            names[f"s{i}"] = (first, last)

        for i, (title, teacher, exam_questions, description, difficulty) in enumerate(D.courses_raw, 1):
            cur.execute("INSERT INTO courses (title, teacher_id, exam_questions, description, difficulty, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                        (title, ids[teacher], exam_questions, description, difficulty, moment(0)))
            ids[f"c{i}"] = cur.fetchone()[0]

        labs: dict[str, list[tuple[int, int, str, str]]] = {}
        for ckey, items in D.labs_data.items():
            labs[ckey] = []
            for number, title, task in items:
                cur.execute("INSERT INTO labs (number, title, task, course_id, min_words, required_sections) "
                            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                            (number, title, task, ids[ckey], LAB_MIN_WORDS, LAB_SECTIONS))
                labs[ckey].append((cur.fetchone()[0], number, title, task))

        for skey, ckey in D.enrollments:
            cur.execute("INSERT INTO students_courses (student_id, course_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (ids[skey], ids[ckey]))
        for skey, ckey, status in D.requests_data:
            cur.execute("INSERT INTO course_requests (student_id, course_id, status, created_at) "
                        "VALUES (%s,%s,%s,%s)", (ids[skey], ids[ckey], status, moment(55)))
        for ckey, tags in D.course_tags_data.items():
            for tag in tags:
                cur.execute("INSERT INTO course_tags (course_id, tag) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            (ids[ckey], tag))
        for skey, tags in D.student_interests_data.items():
            for tag in tags:
                cur.execute("INSERT INTO student_interests (student_id, tag) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            (ids[skey], tag))
        for skey, style, notes in D.preferences_data:
            cur.execute("INSERT INTO student_preferences (student_id, preferred_explanation_style, notes) "
                        "VALUES (%s,%s,%s) ON CONFLICT (student_id) DO NOTHING", (ids[skey], style, notes))

        # тесты: вопросы из банка, неверные ответы выбираются детерминированно
        for skey, ckey, tests in D.test_plan:
            for n, (topic, difficulty, total, correct) in enumerate(tests):
                bank = QUESTIONS[ckey][topic][:total]
                wrong = set(rng.sample(range(total), total - correct))
                cur.execute("INSERT INTO test_results (student_id, course_id, topic, source, difficulty, "
                            "total_questions, correct_answers, wrong_answers, percentage, created_at) "
                            "VALUES (%s,%s,%s,'topic',%s,%s,%s,%s,%s,%s) RETURNING id",
                            (ids[skey], ids[ckey], topic, difficulty, total, correct, total - correct,
                             round(correct / total * 100, 1), moment(8 + n * 9 + rng.random() * 4)))
                result_id = cur.fetchone()[0]
                for num, (question, options, answer) in enumerate(bank, 1):
                    letters = "ABCD"
                    chosen = rng.choice([x for x in letters if x != answer]) if num - 1 in wrong else answer
                    explanation = None
                    if chosen != answer:
                        explanation = (f"Верный ответ — {answer}: «{options[letters.index(answer)]}». "
                                       f"Вариант {chosen} («{options[letters.index(chosen)]}») неверен; "
                                       f"повторите тему «{topic}» в лекциях курса.")
                    cur.execute("INSERT INTO test_result_answers (test_result_id, question_num, question_text, "
                                "options, user_answer, correct_answer, is_correct, explanation) "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                (result_id, num, question,
                                 json.dumps(dict(zip(letters, options)), ensure_ascii=False),
                                 chosen, answer, chosen == answer, explanation))

        # пробный экзамен: ответ и вердикт соответствуют баллу (как у экзаменатора системы)
        attempts: dict[tuple[str, str], int] = {}
        for skey, ckey, completed, scores in D.exam_plan:
            k = attempts[(skey, ckey)] = attempts.get((skey, ckey), 0) + 1
            avg = round(sum(scores) / len(scores), 1) if completed else None
            cur.execute("INSERT INTO exam_results (student_id, course_id, total_questions, avg_score, completed, "
                        "created_at) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                        (ids[skey], ids[ckey], len(scores), avg, completed, moment(40 + k * 6)))
            exam_id = cur.fetchone()[0]
            if not completed:
                continue
            bank = EXAMS[ckey]
            for i, score in enumerate(scores):
                question, good, weak, issue = bank[i % len(bank)]
                verdict = "correct" if score >= 75 else "partial" if score >= 35 else "incorrect"
                answer = good if score >= 75 else weak
                issues = [] if verdict == "correct" else [issue]
                rec = ("Ответ полный, материал усвоен." if verdict == "correct"
                       else f"Дополните ответ: {issue[0].lower() + issue[1:]}.")
                cur.execute("INSERT INTO exam_result_answers (exam_result_id, question_id, question_text, "
                            "user_answer, verdict, recommendation, issues, score) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (exam_id, i + 1, question, answer, verdict, rec,
                             json.dumps(issues, ensure_ascii=False), str(score)))

        # отчёты: текстовые файлы в каталоге загрузок, статусы — решения преподавателя
        reports_dir.mkdir(parents=True, exist_ok=True)
        seeded_reports = []
        for skey, ckey, lab_idx, status, comment in D.reports_raw:
            lab_id, number, title, task = labs[ckey][lab_idx]
            first, last = names[skey]
            text = _report_text(number, title, task, first, last, rng)
            path = reports_dir / f"{uuid.uuid4().hex}.txt"
            path.write_text(text, encoding="utf-8")
            created_files.append(path)
            cur.execute("INSERT INTO reports (lab_id, student_id, status, comment, source_type, filename, file_path, "
                        "text, created_at) VALUES (%s,%s,%s::report_status,%s,'file',%s,%s,%s,%s) RETURNING id",
                        (lab_id, ids[skey], status, comment, f"Отчёт_ЛР{number}_{last}.txt", str(path), text,
                         moment(12 + lab_idx * 14 + rng.random() * 5)))
            seeded_reports.append((cur.fetchone()[0], ids[skey], lab_id, text))

        for skey, ckey, rating in D.ratings_data:
            cur.execute("INSERT INTO course_ratings (student_id, course_id, rating) VALUES (%s,%s,%s) "
                        "ON CONFLICT DO NOTHING", (ids[skey], ids[ckey], rating))

        for skey, ckey, name, messages in D.chats_data:
            cur.execute("INSERT INTO chats (student_id, course_id, name) VALUES (%s,%s,%s) RETURNING id",
                        (ids[skey], ids[ckey], name))
            chat_id = cur.fetchone()[0]
            for role, content in messages:
                cur.execute("INSERT INTO chat_messages (chat_id, role, content) VALUES (%s,%s,%s)",
                            (chat_id, role, content))
        conn.commit()

    try:
        with _connect() as conn, conn.cursor() as cur:
            conn.autocommit = True
            cur.execute("REFRESH MATERIALIZED VIEW course_ranking_stats")
    except Exception as exc:
        logger.warning(f"Не удалось обновить статистику рейтинга курсов: {exc}")

    _index_fingerprints(seeded_reports)
    logger.info(f"Демонстрационные данные созданы: 2 преподавателя, 10 студентов, 10 курсов, "
                f"{len(seeded_reports)} отчётов (пароль совпадает с логином)")
    return True


def _index_fingerprints(reports: list[tuple[int, int, int, str]]) -> None:
    """Отпечатки SimHash отчётов: списанный у демонстрационного студента отчёт будет обнаружен."""
    try:
        from agents.verification.normalizer import TextNormalizer
        from agents.verification.simhash import simhash_bits
        from database.vector.repositories import ReportIndex
        from settings import verification_settings as vcfg
        normalizer, index = TextNormalizer(), ReportIndex()
        for report_id, student_id, lab_id, text in reports:
            bits = simhash_bits(normalizer.lemmas(text), vcfg.simhash_bits, vcfg.simhash_shingle)
            index.add(bits, report_id=report_id, student_id=student_id, lab_id=lab_id)
    except Exception as exc:
        logger.warning(f"Отпечатки демонстрационных отчётов не сохранены: {exc}")


def ensure_materials(attempts: int = 1, delay: float = 30.0) -> int:
    """Индексирует конспекты лекций демонстрационных курсов, у которых ещё нет материалов.

    Возвращает число курсов, оставшихся без материалов."""
    from database.sql import CourseRepository
    from database.vector.repositories import StorageManager
    from rag.indexer import Indexer

    titles = {title: f"c{i}" for i, (title, *_rest) in enumerate(D.courses_raw, 1)}
    missing = -1
    for attempt in range(1, attempts + 1):
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT c.id, c.title, c.storage_id FROM courses c JOIN teachers t ON t.id = c.teacher_id "
                        "WHERE t.login = ANY(%s)", (list(TEACHER_LOGINS),))
            courses = cur.fetchall()
        repo, missing = CourseRepository(), 0
        for course_id, title, storage_id in courses:
            key = titles.get(title)
            if not key:
                continue
            try:
                if storage_id and StorageManager.exists(storage_id) and \
                        StorageManager.get_vector_storage(storage_id).count() > 0:
                    continue
                if not storage_id or not StorageManager.exists(storage_id):
                    storage_id = StorageManager.create_storage()
                    repo.update(course_id, storage_id=storage_id)
                data = LECTURES[key].encode("utf-8")
                file_id, chunks = Indexer(storage_id).add_file(data, LECTURE_FILENAME)
                folder = Path(settings.uploads_dir) / "materials"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{file_id}.txt").write_bytes(data)
                repo.add_course_file(course_id, LECTURE_FILENAME, file_id)
                logger.info(f"Лекции курса «{title}» проиндексированы: {chunks} фрагментов")
            except Exception as exc:
                missing += 1
                logger.warning(f"Лекции курса «{title}» не проиндексированы ({type(exc).__name__}: {exc})")
        if missing == 0:
            return 0
        if attempt < attempts:
            logger.info(f"Без материалов осталось курсов: {missing}; повтор через {delay:.0f} с")
            time.sleep(delay)
    return missing


def auto_seed() -> None:
    """Вызывается при старте сервера (SEED_DEMO=true): наполняет пустую базу и догружает лекции."""
    try:
        if run():
            logger.info("Вход: teacher1/teacher1, teacher2/teacher2, student1/student1 … student10/student10")
        left = ensure_materials(attempts=10, delay=30)
        if left:
            logger.warning(f"Курсов без лекций: {left}. Проверьте ключ эмбеддингов; индексация повторится "
                           "при следующем запуске")
    except Exception as exc:
        logger.exception(f"Наполнение демонстрационными данными не выполнено: {exc}")
