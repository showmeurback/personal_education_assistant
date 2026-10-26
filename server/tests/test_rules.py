from agents.verification.normalizer import TextNormalizer
from agents.verification.rules import LabRequirements, Outcome, apply_rules, build_facts
from fixtures import GOOD_REPORT, OFF_TOPIC_REPORT, TASK


def run(text, **req):
    n = TextNormalizer()
    facts = build_facts(text, n.lemmas(text), n.lemmas(req.get("task", TASK)))
    req.setdefault("task", TASK)
    return {r.rule_id: r for r in apply_rules(facts, LabRequirements(**req))}


def test_good_report_passes_all_rules():
    res = run(GOOD_REPORT, min_words=100, required_sections=["Цель", "Вывод"])
    assert all(r.outcome is Outcome.PASS for r in res.values()), {k: v.message for k, v in res.items()}


def test_empty_report_blocked_by_r1_only():
    res = run("Отчёт.")
    assert list(res) == ["R1"] and res["R1"].outcome is Outcome.BLOCK


def test_min_words_from_lab_settings():
    res = run(GOOD_REPORT, min_words=1000)
    assert res["R2"].outcome is Outcome.BLOCK and res["R2"].threshold == 1000


def test_missing_required_section_is_listed():
    res = run(GOOD_REPORT, required_sections=["Цель", "Листинг программы"])
    assert res["R3"].outcome is Outcome.BLOCK and "Листинг программы" in res["R3"].message


def test_off_topic_report_raises_topic_warning():
    res = run(OFF_TOPIC_REPORT, min_words=50)
    assert res["R6"].outcome is Outcome.WARN


def test_section_must_be_a_heading_not_a_word_in_text():
    text = GOOD_REPORT.replace("Вывод:", "Итог:").replace("подтверждает", "подтверждает; вывод очевиден")
    res = run(text, required_sections=["Вывод"])
    assert res["R3"].outcome is Outcome.BLOCK


def test_requirements_parsed_from_db_text():
    req = LabRequirements.from_db("задание", 50, "Цель работы\nВыводы; Литература")
    assert req.required_sections == ["Цель работы", "Выводы", "Литература"]


def test_section_alternatives():
    """«Вывод|Заключение»: раздел засчитывается по любому из названий (найдено на реальных отчётах)."""
    body = "изучить сортировку массивов и сравнить время работы алгоритмов " * 4
    req = LabRequirements(task="задание", min_words=5, required_sections=["Цель", "Вывод|Заключение"])
    text = "Цель работы\n" + body + "\nЗаключение\nработа выполнена"
    r3 = next(r for r in apply_rules(build_facts(text, text.lower().split(), []), req) if r.rule_id == "R3")
    assert r3.outcome is Outcome.PASS
    text2 = "Цель работы\n" + body
    r3b = next(r for r in apply_rules(build_facts(text2, text2.lower().split(), []), req) if r.rule_id == "R3")
    assert r3b.outcome is Outcome.BLOCK and "«Вывод» или «Заключение»" in r3b.message


def test_section_heading_must_be_whole_word():
    req = LabRequirements(task="задание", min_words=5, required_sections=["Вывод"])
    body = "описание агента и его алгоритма работы с базой знаний " * 4
    for text, ok in (("Выводы\n" + body, True), ("8. ВЫВОД\n" + body, True), ("Вывод:\n" + body, True),
                     ("выводится из даты рождения\n" + body, False)):
        r3 = next(r for r in apply_rules(build_facts(text, text.lower().split(), []), req) if r.rule_id == "R3")
        assert (r3.outcome is Outcome.PASS) is ok, text[:30]


def test_section_heading_plural_form():
    """«Цели работы:» засчитывается как раздел «Цель», «Целый ряд …» — нет (найдено на отложенном наборе)."""
    req = LabRequirements(task="задание", min_words=5, required_sections=["Цель"])
    body = "описание агента и его алгоритма работы с базой знаний " * 4
    for text, ok in (("Цели работы:\n" + body, True), ("Цель:\n" + body, True),
                     ("Целый ряд задач\n" + body, False), ("Целевой показатель\n" + body, False)):
        r3 = next(r for r in apply_rules(build_facts(text, text.lower().split(), []), req) if r.rule_id == "R3")
        assert (r3.outcome is Outcome.PASS) is ok, text[:30]
