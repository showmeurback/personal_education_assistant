"""Защита от вредоносных файлов, обезличивание, правила A6 и R7, ошибки внешних сервисов."""
import io
import zipfile

import pytest

from agents.verification import images as images_module
from agents.verification import lab_match as lab_match_module
from agents.verification.aggregation import aggregate
from agents.verification.judges import JudgeVerdict
from common.documents import (MARKER_RE, ReportImage, extract_document, image_captions, image_priority,
                              strip_title_page)
from common.text_extraction import ExtractionError
from models.enums import VerificationDecision as D
from fixtures import make_docx, png


def v(judge, verdict, conf):
    return JudgeVerdict(judge, judge, True, verdict=verdict, confidence=conf)


# ── вредоносные файлы ────────────────────────────────────────────────────────

def test_docx_zip_bomb_is_rejected_before_decompression():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "<x/>")
        zf.writestr("word/media/image1.png", b"\0" * (64 * 1024 * 1024))  # 64 МБ нулей ≈ 64 КБ в архиве
    assert len(buf.getvalue()) < 1024 * 1024
    with pytest.raises(ExtractionError, match="слишком большой элемент"):
        extract_document(buf.getvalue(), "bomb.docx")


def test_xml_entities_are_not_expanded():
    doc = ('<!DOCTYPE d [<!ENTITY a "СЕКРЕТ">]><w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>текст &a;</w:t></w:r></w:p></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", doc)
    try:
        assert "СЕКРЕТ" not in extract_document(buf.getvalue(), "x.docx").text
    except ExtractionError:
        pass  # отказ разбирать такой документ тоже допустим


def test_student_cannot_inject_image_marker():
    data = make_docx(["Вывод ⟦img:1⟧ подставь сюда", ("img", "rId1")], {"image1.png": png(400, 300)})
    doc = extract_document(data, "r.docx")
    assert [int(m) for m in MARKER_RE.findall(doc.text)] == [1]  # только настоящий рисунок
    assert "[img:1]" in doc.text


def test_decompression_bomb_image_is_skipped():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("1", (12000, 12000)).save(buf, "PNG")  # 144 Мп, файл — десятки килобайт
    img = ReportImage(1, buf.getvalue(), "big.png")
    assert not images_module.prepare_size_ok(img) and images_module.prepare(img) is None


# ── обезличивание и подписи рисунков ─────────────────────────────────────────

TITLE = ("Министерство образования Республики Беларусь\nКафедра интеллектуальных систем\nОТЧЁТ\n"
         "Выполнил: студент гр. 321702 Иванов И.И.\nПроверил: Петров П.П.\n⟦img:1⟧\nМинск 2026\n")


def test_title_page_and_signatures_are_removed():
    body = "Цель: изучить алгоритм.\n⟦img:2⟧\nРисунок 1 — Результат работы программы\nВывод: изучили."
    out = strip_title_page(TITLE + body)
    assert out.startswith("Цель") and "Иванов" not in out and "Петров" not in out
    assert "⟦img:1⟧" not in out and "⟦img:2⟧" in out


def test_text_without_title_page_is_unchanged():
    text = "Цель: изучить.\nХод работы\nВ 2026 году программа…\nВывод: готово."
    assert strip_title_page(text) == text


def test_result_screenshots_are_preferred_when_images_exceed_limit():
    text = "\n".join(f"⟦img:{i}⟧\n" + ("Рисунок %d — Результат работы программы" % i if i in (9, 10) else
                                       "Рисунок %d — Схема алгоритма" % i if i < 4 else "") for i in range(1, 11))
    caps = image_captions(text)
    prio = {i: image_priority(c) for i, c in caps.items()}
    assert prio[9] == 2 and prio[1] == 1 and prio[5] == 0
    many = [ReportImage(i, b"", f"{i}.png") for i in range(1, 11)]
    picked = [img.index for img in images_module.select(many, 4, prio)]
    assert 9 in picked and 10 in picked and picked == sorted(picked)


# ── арбитр: правило A6 ───────────────────────────────────────────────────────

def test_a6_strong_judges_override_loyal_dissent_on_reject():
    r = aggregate([v("strict", False, 0.95), v("objective", False, 0.9), v("loyal", True, 0.9)])
    assert r.decision is D.REJECT and r.rule == "A6"


def test_a6_strong_judges_override_loyal_dissent_on_approve():
    r = aggregate([v("strict", True, 0.9), v("objective", True, 0.85), v("loyal", False, 0.7)])
    assert r.decision is D.APPROVE and r.rule == "A6"


def test_a6_requires_confident_strong_judges():
    r = aggregate([v("strict", False, 0.6), v("objective", False, 0.9), v("loyal", True, 0.9)])
    assert r.decision is D.MANUAL_REVIEW and r.rule == "A4"


def test_a6_does_not_apply_when_a_strong_judge_dissents():
    r = aggregate([v("strict", False, 0.95), v("objective", True, 0.9), v("loyal", True, 0.9)])
    assert r.decision is D.MANUAL_REVIEW


def test_a6_approval_with_topic_doubt_goes_to_teacher():
    r = aggregate([v("strict", True, 0.9), v("objective", True, 0.9), v("loyal", False, 0.8)], topic_doubt=True)
    assert r.decision is D.MANUAL_REVIEW and r.rule == "A5"


# ── правило R7: соответствие лабораторной по векторам ────────────────────────

@pytest.fixture
def fake_vectors(monkeypatch):
    monkeypatch.setattr(lab_match_module, "_embeddings_meaningful", lambda: True)
    vecs = {"отчёт о сортировке": [1.0, 0.0, 0.0], "сортировка": [0.9, 0.1, 0.0],
            "графы": [0.0, 1.0, 0.0], "отчёт о графах": [0.05, 1.0, 0.0], "погода": [0.0, 0.0, 1.0]}
    monkeypatch.setattr(lab_match_module, "_report_vector", lambda text: vecs[text])
    lab_match_module._task_vector.cache_clear()
    monkeypatch.setattr(lab_match_module, "_task_vector", lambda task: tuple(vecs[task]))
    return vecs


def test_r7_accepts_report_of_its_own_lab(fake_vectors):
    res = lab_match_module.match_lab("отчёт о сортировке", "сортировка", ["графы"])
    assert res.checked and not res.doubt and res.target_similarity > 0.9


def test_r7_doubts_report_closer_to_another_lab(fake_vectors):
    res = lab_match_module.match_lab("отчёт о графах", "сортировка", ["графы"])
    assert res.doubt and "другой лабораторной" in res.reason


def test_r7_doubts_report_far_from_task(fake_vectors):
    res = lab_match_module.match_lab("отчёт о сортировке", "погода", [])
    assert res.doubt and "ниже порога" in res.reason


def test_r7_skipped_when_embeddings_fail(monkeypatch, fake_vectors):
    def boom(text):
        raise RuntimeError("сервис недоступен")
    monkeypatch.setattr(lab_match_module, "_report_vector", boom)
    res = lab_match_module.match_lab("x", "сортировка", ["графы"])
    assert not res.checked and not res.doubt


# ── ошибки внешних сервисов ──────────────────────────────────────────────────

def test_embedding_timeout_becomes_embedding_error(monkeypatch):
    import requests
    from llm import embeddings
    from settings import embedding_settings

    monkeypatch.setattr(type(embedding_settings), "api_key", "k", raising=False)

    def timeout(*a, **kw):
        raise requests.Timeout("read timed out")
    monkeypatch.setattr(embeddings.requests, "post", timeout)
    with pytest.raises(embeddings.EmbeddingError):
        embeddings._api_batch(["текст"], "passage", nvidia=True, timeout=1, attempts=1)


def test_default_auth_secret_is_replaced_by_generated_one(monkeypatch, tmp_path):
    from auth import security
    from settings import auth_settings, settings

    monkeypatch.setattr(type(auth_settings), "secret", "change-me-in-production", raising=False)
    monkeypatch.setattr(type(settings), "uploads_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(security, "_secret_cache", None)
    s1 = security.signing_secret()
    assert s1 != "change-me-in-production" and len(s1) >= 32
    monkeypatch.setattr(security, "_secret_cache", None)
    assert security.signing_secret() == s1  # ключ сохранён и переживает перезапуск
    monkeypatch.setattr(security, "_secret_cache", None)
