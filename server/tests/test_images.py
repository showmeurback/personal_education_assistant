"""Извлечение рисунков из DOCX и агент описания изображений (заглушка модели зрения)."""
from agents.verification import images as images_module
from agents.verification.pipeline import VerificationPipeline
from agents.verification.rules import LabRequirements
from common.documents import MARKER_RE, extract_document, insert_descriptions, strip_markers
from database.vector.repositories.report_index import InMemoryReportIndex
from fixtures import GOOD_REPORT, TASK, make_docx, png

def test_docx_images_are_marked_in_document_order():
    data = make_docx(["Ход работы", ("img", "rId1"), "Рисунок 1 — Окно программы", ("img", "rId2"),
                      ("img", "rId1"), "Вывод"], {"image1.png": png(400, 300), "image2.png": png(500, 300, "red")})
    doc = extract_document(data, "report.docx")
    assert [i.index for i in doc.images] == [1, 2]
    assert [int(m) for m in MARKER_RE.findall(doc.text)] == [1, 2]  # повтор рисунка не дублируется
    assert doc.text.index("⟦img:1⟧") < doc.text.index("Рисунок 1") < doc.text.index("⟦img:2⟧")
    assert "⟦" not in doc.plain and "Рисунок 1 — Окно программы" in doc.plain


def test_descriptions_replace_markers_and_missing_ones_are_dropped():
    text = "Ход ⟦img:1⟧ Рисунок 1 ⟦img:2⟧ Вывод"
    out = insert_descriptions(text, {1: "Скриншот консоли"})
    assert "[Изображение 1, автоматическое описание: Скриншот консоли]" in out
    assert "⟦" not in out and "Изображение 2" not in out
    assert strip_markers(text) == "Ход Рисунок 1 Вывод"


def test_small_images_are_skipped_and_selection_is_even():
    from common.documents import ReportImage
    icon = ReportImage(1, png(40, 40), "icon.png")
    assert images_module.prepare(icon) is None and not images_module.prepare_size_ok(icon)
    many = [ReportImage(i, b"", f"{i}.png") for i in range(1, 21)]
    picked = images_module.select(many, 5)
    assert [i.index for i in picked] == [1, 5, 9, 13, 17]


async def test_pipeline_inserts_image_descriptions_for_judges(monkeypatch, tmp_path):
    from common.documents import ReportImage
    seen = {}
    from agents.verification import pipeline as pipeline_module
    original = pipeline_module.run_judge

    async def spy(judge, requirements, report_text):
        seen[judge] = report_text
        return await original(judge, requirements, report_text)

    monkeypatch.setattr(pipeline_module, "run_judge", spy)
    monkeypatch.setattr(images_module, "_cache_path", lambda sha: tmp_path / f"{sha}.json")
    images_module._memory_cache.clear()
    text = GOOD_REPORT + "\n⟦img:1⟧\nРисунок 1 — Результат работы программы"
    req = LabRequirements(task=TASK, min_words=60, required_sections=["Цель", "Вывод"])
    r = await VerificationPipeline(InMemoryReportIndex()).run(
        text=text, images=[ReportImage(1, png(640, 480), "image1.png")],
        requirements=req, student_id=1, lab_id=1)
    step = next(s for s in r.protocol if s["title"] == "Описание изображений")
    assert step["kind"] == "neural" and step["details"]["described"] == 1
    assert r.vision_calls == 1
    assert all("Изображение 1, автоматическое описание" in t for t in seen.values())
    # повторная проверка того же рисунка берёт описание из кэша
    again = await VerificationPipeline(InMemoryReportIndex()).run(
        text=text, images=[ReportImage(1, png(640, 480), "image1.png")],
        requirements=req, student_id=2, lab_id=1)
    assert again.vision_calls == 0


async def test_report_without_images_has_no_image_step():
    req = LabRequirements(task=TASK, min_words=60, required_sections=["Цель", "Вывод"])
    r = await VerificationPipeline(InMemoryReportIndex()).run(
        text=GOOD_REPORT, requirements=req, student_id=1, lab_id=1)
    assert all(s["title"] != "Описание изображений" for s in r.protocol)
