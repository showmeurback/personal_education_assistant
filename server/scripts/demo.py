"""Наполнение запущенной системы демонстрационными данными через REST API.

Создаёт преподавателя, три курса с материалами и лабораторными работами,
шесть студентов и сдаёт отчёты из размеченного набора эксперимента
(experiments/dataset.json), чтобы в очереди преподавателя были все виды решений.

Запуск:  python scripts/demo.py http://localhost:8000
Пароль всех демонстрационных пользователей: demo1234
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
from labs import LABS  # noqa: E402

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/") + "/api/v1"
PASSWORD = "demo1234"
SUFFIX = uuid.uuid4().hex[:4]

COURSES = [
    {"title": "Алгоритмы и структуры данных", "difficulty": "beginner", "tags": ["Алгоритмы", "Программирование"],
     "description": "Сортировка и поиск, оценка вычислительной сложности, основные структуры данных.",
     "exam_questions": "1. Опишите алгоритм быстрой сортировки и его сложность.\n"
                       "2. Чем сортировка пузырьком хуже быстрой сортировки?\n"
                       "3. Что такое асимптотическая сложность алгоритма?",
     "lab": 1,
     "material": (
         "Лекция 3. Алгоритмы сортировки.\n"
         "Сортировка пузырьком последовательно сравнивает соседние элементы массива и меняет их местами, если они "
         "стоят в неправильном порядке. После каждого прохода наибольший элемент оказывается в конце. Алгоритм "
         "выполняет порядка n^2 сравнений в среднем и худшем случаях, поэтому применим только для небольших массивов.\n"
         "Быстрая сортировка (quicksort) выбирает опорный элемент, разбивает массив на элементы меньше и больше "
         "опорного и рекурсивно сортирует обе части. Средняя сложность O(n log n), худшая — O(n^2), она возникает "
         "при неудачном выборе опорного элемента, например на уже отсортированном массиве при выборе первого "
         "элемента. Для защиты используют случайный опорный элемент или медиану трёх.\n"
         "Сортировка слиянием делит массив пополам, сортирует половины и сливает их; её сложность O(n log n) "
         "в любом случае, но она требует O(n) дополнительной памяти.\n"
         "Для экспериментального сравнения алгоритмов измеряют время работы на массивах разного размера и строят "
         "график зависимости времени от n. Квадратичный алгоритм при увеличении n в 10 раз замедляется примерно в 100 "
         "раз, а алгоритм n log n — примерно в 13 раз.\n")},
    {"title": "Базы данных", "difficulty": "intermediate", "tags": ["Базы данных", "Программирование"],
     "description": "Реляционная модель, нормализация, проектирование схем и язык SQL.",
     "exam_questions": "1. Что такое функциональная зависимость?\n2. Сформулируйте требования третьей нормальной формы.",
     "lab": 2,
     "material": (
         "Лекция 5. Нормализация.\n"
         "Первая нормальная форма требует атомарности значений атрибутов. Вторая нормальная форма требует, чтобы "
         "каждый неключевой атрибут полностью зависел от первичного ключа. Третья нормальная форма требует "
         "отсутствия транзитивных зависимостей неключевых атрибутов от ключа. Нормализация устраняет аномалии "
         "вставки, обновления и удаления.\n")},
    {"title": "Компьютерные сети", "difficulty": "intermediate", "tags": ["Сети", "Программирование"],
     "description": "Модель TCP/IP, транспортные протоколы, сокеты и измерение характеристик сети.",
     "exam_questions": "1. Чем TCP отличается от UDP?\n2. Как работает тройное рукопожатие?",
     "lab": 3,
     "material": (
         "Лекция 7. Транспортный уровень.\n"
         "TCP устанавливает соединение тройным рукопожатием, подтверждает доставку сегментов, повторно передаёт "
         "потерянные данные и управляет потоком с помощью скользящего окна. UDP не устанавливает соединения и не "
         "гарантирует доставку, зато имеет меньшие накладные расходы и задержку.\n")},
]

STUDENTS = [("Анна", "Ковалёва", ["Алгоритмы", "Программирование"]),
            ("Максим", "Новиков", ["Алгоритмы"]),
            ("Дарья", "Лебедева", ["Базы данных", "Программирование"]),
            ("Илья", "Морозов", ["Сети"]),
            ("Олег", "Соколов", ["Программирование"]),
            ("Елена", "Волкова", ["Алгоритмы", "Сети"])]

# какие отчёты набора сдаёт каждый студент по первой лабораторной
SUBMISSIONS = ["original", "copy_exact", "weak_ok", "off_topic", "keywords", "injection"]


def call(method, path, token=None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, BASE + path, headers=headers, timeout=600, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:300]}")
    return r.json()


def main() -> None:
    teacher = call("POST", "/auth/register/teacher", json={
        "login": f"ivanov_{SUFFIX}", "password": PASSWORD, "first_name": "Сергей", "last_name": "Иванов"})
    teacher["login"] = f"ivanov_{SUFFIX}"
    tt = teacher["token"]
    courses = []
    for c in COURSES:
        cid = call("POST", "/courses", tt, json={k: c[k] for k in
                                                  ("title", "description", "difficulty", "tags", "exam_questions")})["course_id"]
        call("POST", f"/courses/{cid}/files", tt,
             files={"files": (f"lecture_{c['lab']}.txt", c["material"].encode(), "text/plain")})
        lab = LABS[c["lab"]]
        lab_id = call("POST", f"/courses/{cid}/labs", tt, json={
            "number": 1, "title": lab["title"], "task": lab["task"], "min_words": lab["min_words"],
            "required_sections": "\n".join(lab["required_sections"])})["id"]
        courses.append((cid, lab_id))
        print("курс", c["title"], cid, "лабораторная", lab_id)

    students = []
    for i, (first, last, interests) in enumerate(STUDENTS):
        s = call("POST", "/auth/register/student", json={
            "login": f"student{i + 1}_{SUFFIX}", "password": PASSWORD, "first_name": first, "last_name": last,
            "interests": interests})
        s["login"] = f"student{i + 1}_{SUFFIX}"
        students.append(s)
        for cid, _ in courses[:1] + ([courses[1]] if i % 2 else []) + ([courses[2]] if i % 3 == 0 else []):
            req = call("POST", f"/courses/{cid}/requests", s["token"])
            call("POST", f"/course-requests/{req['request_id']}/approve", tt)

    dataset = json.loads((ROOT / "experiments/dataset.json").read_text(encoding="utf-8"))
    lab1 = [d for d in dataset if d["lab"] == 1]
    cid, lab_id = courses[0]
    for s, cat in zip(students, SUBMISSIONS):
        text = next(d["text"] for d in lab1 if d["category"] == cat)
        res = call("POST", f"/labs/{lab_id}/reports", s["token"],
                   files={"file": (f"report_{cat}.txt", text.encode(), "text/plain")})
        print(f"{s['login']:<18} {cat:<11} → {res['status']:<14} ({res['decided_by']}, LLM: {res['llm_calls']})")

    print(f"\nПреподаватель: {teacher['login']} / {PASSWORD}")
    print("Студенты:", ", ".join(s["login"] for s in students), f"/ {PASSWORD}")


if __name__ == "__main__":
    main()
