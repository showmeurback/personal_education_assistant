"""Сквозные сценарии против запущенной системы (docker compose up).

Запуск:  E2E_BASE_URL=http://localhost:8000 pytest -m e2e -v
Идентификаторы сценариев (E1…E21) используются в пояснительной записке.
Группы: T — типичные, B — граничные, N — отрицательные.
"""
import os
import uuid

import pytest
import requests

from fixtures import GOOD_REPORT, OFF_TOPIC_REPORT, PARAPHRASED_REPORT, TASK, make_docx, png

BASE = os.environ.get("E2E_BASE_URL")
pytestmark = [pytest.mark.e2e, pytest.mark.skipif(not BASE, reason="E2E_BASE_URL не задан")]
API = f"{BASE}/api/v1" if BASE else ""


def call(method, path, token=None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, API + path, headers=headers, timeout=300, **kw)


@pytest.fixture(scope="module")
def world():
    """Преподаватель, курс с материалами и лабораторной, три зачисленных студента."""
    suffix = uuid.uuid4().hex[:6]
    t = call("POST", "/auth/register/teacher", json={"login": f"t_{suffix}", "password": "pass1234",
                                                      "first_name": "Пётр", "last_name": "Тестов"}).json()
    course = call("POST", "/courses", t["token"], json={
        "title": "Алгоритмы сортировки", "description": "Курс об алгоритмах сортировки и их сложности",
        "difficulty": "beginner", "tags": ["Алгоритмы"],
        "exam_questions": "1. Что такое быстрая сортировка?\n2. Какова сложность сортировки пузырьком?"}).json()
    cid = course["course_id"]
    material = ("Быстрая сортировка — алгоритм, основанный на выборе опорного элемента и разбиении массива. "
                "Средняя сложность O(n log n), худшая O(n^2). Сортировка пузырьком сравнивает соседние "
                "элементы и имеет сложность O(n^2). ") * 25
    up = call("POST", f"/courses/{cid}/files", t["token"],
              files={"files": ("lecture.txt", material.encode(), "text/plain")})
    assert up.status_code == 200, up.text
    lab = call("POST", f"/courses/{cid}/labs", t["token"], json={
        "number": 1, "title": "Быстрая сортировка", "task": TASK, "min_words": 60,
        "required_sections": "Цель\nВывод"}).json()
    students = []
    for i in range(4):
        s = call("POST", "/auth/register/student", json={"login": f"s{i}_{suffix}", "password": "pass1234",
                                                          "first_name": f"Студент{i}", "last_name": "Тестов",
                                                          "interests": ["Алгоритмы"]}).json()
        req = call("POST", f"/courses/{cid}/requests", s["token"]).json()
        call("POST", f"/course-requests/{req['request_id']}/approve", t["token"])
        students.append(s)
    return {"teacher": t, "cid": cid, "lab": lab["id"], "students": students}


def submit(world, student_idx, text, name="report.txt"):
    s = world["students"][student_idx]
    return call("POST", f"/labs/{world['lab']}/reports?wait=true", s["token"],
                files={"file": (name, text.encode(), "text/plain")})


# ── T: типичные сценарии ──────────────────────────────────────────────────────

def test_E1_T_correct_report_passes_hybrid_check(world):
    r = submit(world, 0, GOOD_REPORT)
    assert r.status_code == 200, r.text
    body = r.json()
    world["first_report"] = body["report_id"]
    assert body["status"] in ("pending", "manual-review")
    assert [s["kind"] for s in body["protocol"]][:3] == ["symbolic"] * 3


def test_E2_T_teacher_sees_queue_and_full_protocol(world):
    t = world["teacher"]["token"]
    queue = call("GET", "/teacher/reports/queue", t).json()["reports"]
    assert any(r["report_id"] == world["first_report"] for r in queue)
    rep = call("GET", f"/reports/{world['first_report']}", t).json()
    assert rep["check"]["protocol"] and rep["report"]["text"]


def test_E3_T_teacher_approves_report(world):
    t = world["teacher"]["token"]
    assert call("POST", f"/reports/{world['first_report']}/status", t, json={"status": "approved"}).status_code == 200
    mine = call("GET", f"/labs/{world['lab']}/my-reports", world["students"][0]["token"]).json()["reports"]
    assert mine[0]["status"] == "approved"


def test_E4_T_rag_chat_answers_with_sources(world):
    tok = world["students"][0]["token"]
    chat = call("POST", "/chats", tok, json={"course_id": world["cid"]}).json()
    r = call("POST", f"/chats/{chat['chat_id']}/messages", tok, json={"message": "Что такое быстрая сортировка?"})
    assert r.status_code == 200 and r.json()["response"]


def test_E5_T_test_generation_and_deterministic_grading(world):
    tok = world["students"][0]["token"]
    gen = call("POST", f"/courses/{world['cid']}/tests/generate", tok,
               json={"topic": "быстрая сортировка", "num_questions": 3, "difficulty": "easy"})
    assert gen.status_code == 200, gen.text
    test = gen.json()
    res = call("POST", f"/tests/{test['test_id']}/submit", tok, json={"answers": ["A"] * test["total_questions"]}).json()
    assert 0 <= res["percentage"] <= 100 and res["grade"] is not None


def test_E6_T_exam_evaluates_answers(world):
    tok = world["students"][0]["token"]
    ex = call("POST", f"/courses/{world['cid']}/exam/start", tok, json={"question_count": 1}).json()
    assert "reference_answer" not in ex["question"]
    a = call("POST", f"/courses/{world['cid']}/exam/answer", tok,
             json={"exam_id": ex["exam_id"], "answer": "Быстрая сортировка выбирает опорный элемент и рекурсивно "
                                                       "разбивает массив, средняя сложность n log n."}).json()
    assert a["evaluation"]["verdict"] in ("correct", "partial", "incorrect") and a["completed"]


def test_E7_T_recommendations_are_explained(world):
    rec = call("GET", "/me/recommendations", world["students"][1]["token"]).json()
    assert "recommended" in rec
    for c in rec["recommended"] + rec["other"][:3]:
        assert "signals" in c and "explanation" in c


# ── B: граничные сценарии ─────────────────────────────────────────────────────

def test_E8_B_verbatim_copy_rejected_by_simhash_without_llm(world):
    body = submit(world, 1, GOOD_REPORT, "copy.txt").json()
    assert body["status"] == "ai-rejected" and body["decided_by"] == "simhash" and body["llm_calls"] == 0


def test_E9_B_paraphrase_passes_filter_and_is_judged_by_llm(world):
    body = submit(world, 2, PARAPHRASED_REPORT, "para.txt").json()
    assert body["decided_by"] == "judges" and body["llm_calls"] >= 3


def test_E10_B_off_topic_report_not_auto_approved(world):
    body = submit(world, 1, OFF_TOPIC_REPORT, "rome.txt").json()
    assert body["status"] in ("ai-rejected", "manual-review"), body


def test_E11_B_resubmission_blocked_while_pending(world):
    # у студента 2 отчёт на проверке/ручной проверке после E9 — повторная отправка запрещена
    mine = call("GET", f"/labs/{world['lab']}/my-reports", world["students"][2]["token"]).json()["reports"]
    if mine[0]["status"] in ("pending", "manual-review"):
        r = submit(world, 2, GOOD_REPORT, "again.txt")
        assert r.status_code == 409


# ── N: отрицательные сценарии ─────────────────────────────────────────────────

def test_E12_N_formally_invalid_report_rejected_by_rules(world):
    body = submit(world, 3, "Цель: сделать.\nВывод: сделал работу.", "short.txt").json()
    assert body["status"] == "ai-rejected" and body["decided_by"] == "rules" and body["llm_calls"] == 0


def test_E13_N_unsupported_file_format(world):
    r = call("POST", f"/labs/{world['lab']}/reports", world["students"][3]["token"],
             files={"file": ("report.exe", b"MZ\x90\x00", "application/octet-stream")})
    assert r.status_code == 400


def test_E14_N_closed_google_doc_link(world):
    r = call("POST", f"/labs/{world['lab']}/reports", world["students"][3]["token"],
             data={"url": "https://example.com/not-a-doc"})
    assert r.status_code == 400


def test_E15_N_access_control(world):
    s1, s2, t = world["students"][0]["token"], world["students"][1]["token"], world["teacher"]["token"]
    assert call("GET", "/me/courses").status_code == 401
    assert call("GET", f"/reports/{world['first_report']}", s2).status_code == 403
    assert call("GET", f"/courses/{world['cid']}/students", s1).status_code == 403
    assert call("POST", f"/reports/{world['first_report']}/status", s1, json={"status": "approved"}).status_code == 403
    assert call("GET", f"/courses/{world['cid']}/analytics", t).status_code == 200


def test_E16_N_invalid_input_validation(world):
    t = world["teacher"]["token"]
    assert call("POST", "/courses", t, json={"title": "", "difficulty": "x"}).status_code == 422
    assert call("POST", "/auth/login", json={"login": "nobody", "password": "x", "role": "student"}).status_code == 401
    assert call("POST", f"/tests/{uuid.uuid4().hex}/submit", world["students"][0]["token"], json={"answers": []}).status_code == 400


def test_E17_T_docx_screenshot_is_described_for_judges(world):
    """Рисунок из DOCX описывается моделью зрения, описание видно в протоколе."""
    shot = png(640, 360, "white", "Terminal\n$ python quicksort.py\nInput: [5, 3, 8, 1, 2]\n"
                                   "Sorted: [1, 2, 3, 5, 8]\nComparisons: 7")
    paragraphs = [p for p in GOOD_REPORT.split("\n") if p.strip()]
    data = make_docx(paragraphs[:-1] + [("img", "rId1"), "Рисунок 1 — Результат работы программы",
                                        paragraphs[-1]], {"image1.png": shot})
    # отдельная лабораторная: текст GOOD_REPORT по первой уже сдан, и SimHash отклонил бы его до описания
    lab2 = call("POST", f"/courses/{world['cid']}/labs", world["teacher"]["token"], json={
        "number": 2, "title": "Быстрая сортировка (с рисунками)", "task": TASK, "min_words": 60,
        "required_sections": "Цель\nВывод"}).json()
    s = world["students"][3]
    r = call("POST", f"/labs/{lab2['id']}/reports?wait=true", s["token"],
             files={"file": ("report.docx", data,
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 200, r.text
    step = next(st for st in r.json()["protocol"] if st["title"] == "Описание изображений")
    assert step["kind"] == "neural" and step["details"]["described"] == 1
    assert step["details"]["descriptions"][0]["description"]


def _new_lab_with_student(world, number):
    t = world["teacher"]["token"]
    lab = call("POST", f"/courses/{world['cid']}/labs", t, json={
        "number": number, "title": f"Быстрая сортировка ({number})", "task": TASK, "min_words": 60,
        "required_sections": "Цель\nВывод"}).json()
    suffix = uuid.uuid4().hex[:6]
    s = call("POST", "/auth/register/student", json={"login": f"q{number}_{suffix}", "password": "pass1234",
                                                      "first_name": "Очередь", "last_name": "Тестов",
                                                      "interests": ["Алгоритмы"]}).json()
    req = call("POST", f"/courses/{world['cid']}/requests", s["token"]).json()
    call("POST", f"/course-requests/{req['request_id']}/approve", t)
    return lab["id"], s["token"]


def test_E18_T_background_check_and_polling(world):
    """Без wait отчёт сразу получает статус «checking» (202), результат появляется позже."""
    import time
    lab_id, tok = _new_lab_with_student(world, 3)
    r = call("POST", f"/labs/{lab_id}/reports", tok, files={"file": ("r.txt", GOOD_REPORT.encode(), "text/plain")})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "checking"
    deadline = time.time() + 240
    while time.time() < deadline:
        rep = call("GET", f"/reports/{body['report_id']}", tok).json()
        if rep["report"]["status"] != "checking":
            break
        time.sleep(2)
    assert rep["report"]["status"] in ("pending", "manual-review", "ai-rejected")
    assert rep["check"] and rep["check"]["protocol"]


def test_E19_B_double_click_creates_one_report(world):
    """Два одновременных запроса сдачи: создаётся один отчёт, второй получает 409."""
    from concurrent.futures import ThreadPoolExecutor
    lab_id, tok = _new_lab_with_student(world, 4)

    def send(_):
        return call("POST", f"/labs/{lab_id}/reports", tok,
                    files={"file": ("r.txt", GOOD_REPORT.encode(), "text/plain")}).status_code

    with ThreadPoolExecutor(2) as ex:
        codes = sorted(ex.map(send, range(2)))
    assert codes == [202, 409], codes
    mine = call("GET", f"/labs/{lab_id}/my-reports", tok).json()["reports"]
    assert len(mine) == 1


def test_E20_T_weak_topics_map_after_test(world):
    """Карта пробелов строится по результатам теста (E5) и экзамена (E6) студента."""
    tok = world["students"][0]["token"]
    r = call("GET", f"/courses/{world['cid']}/weak-topics", tok)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence_total"] >= 1 and "method" in body
    for t in body["topics"]:
        assert 0 <= t["mastery"] < 0.7 and t["level"]
    other = call("GET", f"/courses/{world['cid']}/weak-topics", world["teacher"]["token"])
    assert other.status_code == 403


def test_E21_T_rag_chat_streams_steps_and_text(world):
    """Потоковый ответ ассистента: шаги агента и текст приходят по частям, ответ сохраняется в истории."""
    import json as _json
    tok = world["students"][3]["token"]
    chat = call("POST", "/chats", tok, json={"course_id": world["cid"]}).json()
    events = []
    with requests.post(f"{API}/chats/{chat['chat_id']}/messages/stream", stream=True, timeout=300,
                       headers={"Authorization": f"Bearer {tok}"},
                       json={"message": "Какова сложность сортировки пузырьком?"}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                events.append(_json.loads(line[5:]))
    kinds = [e["type"] for e in events]
    assert "error" not in kinds, events
    assert kinds[0] == "step" and kinds[-1] == "done" and kinds.count("token") > 1
    done = events[-1]
    assert done["response"].strip() and "Поиск по материалам курса" in done["tools"]
    history = call("GET", f"/chats/{chat['chat_id']}/messages", tok).json()
    assert [m["role"] for m in history] == ["human", "ai"] and history[1]["content"] == done["response"]
    # время отправки: вопрос — момент запроса, ответ — момент готовности (UTC, ISO 8601)
    from datetime import datetime
    asked, answered = (datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")) for m in history)
    assert asked <= answered and done["asked_at"] == history[0]["created_at"]
    # инструменты и источники ответа сохраняются в истории
    assert history[1]["tools"] == done["tools"] and history[1]["sources"] == done["sources"]


def test_E22_T_chat_can_be_pinned(world):
    """Закреплённый чат идёт в списке первым, после открепления возвращается на место по дате."""
    tok = world["students"][3]["token"]
    first = call("POST", "/chats", tok, json={"course_id": world["cid"]}).json()["chat_id"]
    call("POST", "/chats", tok, json={"course_id": world["cid"]})
    assert call("PUT", f"/chats/{first}/pin", tok, json={"pinned": True}).json()["pinned"] is True
    chats = call("GET", "/me/chats", tok).json()
    assert chats[0]["chat_id"] == first and chats[0]["pinned"] is True
    call("PUT", f"/chats/{first}/pin", tok, json={"pinned": False})
    chats = call("GET", "/me/chats", tok).json()
    assert chats[0]["chat_id"] != first and not any(c["pinned"] for c in chats if c["chat_id"] == first)
    other = world["students"][0]["token"]
    assert call("PUT", f"/chats/{first}/pin", other, json={"pinned": True}).status_code == 404
