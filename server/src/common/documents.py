"""Извлечение текста отчёта вместе с изображениями.

Изображения (скриншоты программы, графики, схемы) несут значимую часть отчёта о
лабораторной работе, а при извлечении «только текста» от них остаются лишь подписи.
Здесь текст DOCX собирается в порядке документа, а на месте каждого рисунка
ставится маркер ``⟦img:N⟧``; для PDF маркеры ставятся в конце страницы, на
которой находится изображение. Маркеры позволяют затем вставить описание рисунка
рядом с его подписью, а для продукционных правил и SimHash они удаляются
(``ExtractedDocument.plain``), поэтому символьные признаки не меняются.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .text_extraction import (ExtractionError, SUPPORTED_EXTENSIONS, UnsupportedFileError, _decode_text,
                              check_zip_limits, normalize_whitespace)

MARKER = "⟦img:{}⟧"
MARKER_RE = re.compile(r"⟦img:(\d+)⟧")
# символы маркера в тексте самого документа заменяются, чтобы студент не мог
# вставить «маркер» и подставить описание рисунка в произвольное место
_MARKER_CHARS = str.maketrans({"⟦": "[", "⟧": "]"})


def _clean(text: str) -> str:
    return (text or "").translate(_MARKER_CHARS)
# форматы, которые принимает модель зрения; EMF/WMF (векторные вставки Office) пропускаются
_RASTER = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_V = "{urn:schemas-microsoft-com:vml}"
_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"


@dataclass
class ReportImage:
    index: int          # номер по порядку в документе (с 1)
    data: bytes
    name: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass
class ExtractedDocument:
    text: str                                   # текст с маркерами ⟦img:N⟧
    images: list[ReportImage] = field(default_factory=list)

    @property
    def plain(self) -> str:
        """Текст без маркеров — для правил, SimHash и хранения."""
        return strip_markers(self.text)


def strip_markers(text: str) -> str:
    return normalize_whitespace(MARKER_RE.sub("", text or ""))


def insert_descriptions(text: str, descriptions: dict[int, str]) -> str:
    """Заменяет маркеры описаниями рисунков; маркеры без описания удаляются."""
    def repl(m: re.Match) -> str:
        d = descriptions.get(int(m.group(1)))
        return f"\n[Изображение {m.group(1)}, автоматическое описание: {d}]\n" if d else ""
    return normalize_whitespace(MARKER_RE.sub(repl, text or ""))


def extract_document(data: bytes, filename: str) -> ExtractedDocument:
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"Формат файла «{filename}» не поддерживается. Допустимы: PDF, DOCX, TXT.")
    try:
        if ext == ".docx":
            check_zip_limits(data, filename)
            return _docx(data)
        if ext == ".pdf":
            return _pdf(data)
        return ExtractedDocument(normalize_whitespace(_clean(_decode_text(data))))
    except (UnsupportedFileError, ExtractionError):
        raise
    except Exception as exc:  # повреждённый файл
        raise ExtractionError(f"Не удалось прочитать файл «{filename}»: {exc}") from exc


def _xml_parser():
    """Разбор XML без подстановки сущностей и без обращения к сети (защита от XXE)."""
    from lxml import etree

    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


def _docx(data: bytes) -> ExtractedDocument:
    from lxml import etree

    zf = zipfile.ZipFile(io.BytesIO(data))
    rels: dict[str, str] = {}
    try:
        for rel in etree.fromstring(zf.read("word/_rels/document.xml.rels"), parser=_xml_parser()).iter(_PKG_REL):
            if rel.get("TargetMode") != "External":
                rels[rel.get("Id")] = rel.get("Target", "")
    except KeyError:
        pass
    body = etree.fromstring(zf.read("word/document.xml"), parser=_xml_parser()).find(f"{_W}body")
    out: list[str] = []
    images: list[ReportImage] = []
    seen: dict[str, int] = {}

    def image(rid: str | None) -> None:
        target = rels.get(rid or "")
        if not target:
            return
        path = str(PurePosixPath("word") / target) if not target.startswith("/") else target.lstrip("/")
        path = str(PurePosixPath(path))  # «word/../media» и т. п.
        if PurePosixPath(path).suffix.lower() not in _RASTER:
            return
        try:
            blob = zf.read(path)
        except KeyError:
            return
        h = hashlib.sha256(blob).hexdigest()
        if h in seen:  # повтор того же рисунка — один маркер на первое вхождение
            return
        idx = len(images) + 1
        seen[h] = idx
        images.append(ReportImage(idx, blob, PurePosixPath(path).name))
        out.append(f" {MARKER.format(idx)} ")

    def walk(el) -> None:
        tag = el.tag
        if tag == _MC_FALLBACK or tag == f"{_W}delText":
            return
        if tag == f"{_W}t":
            out.append(_clean(el.text))
        elif tag == f"{_W}tab":
            out.append("\t")
        elif tag in (f"{_W}br", f"{_W}cr"):
            out.append("\n")
        elif tag == f"{_A}blip":
            image(el.get(f"{_R}embed"))
        elif tag == f"{_V}imagedata":
            image(el.get(f"{_R}id"))
        for child in el:
            walk(child)
        if tag == f"{_W}p":
            out.append("\n")
        elif tag == f"{_W}tc":
            out.append("\t")

    if body is not None:
        walk(body)
    return ExtractedDocument(normalize_whitespace("".join(out)), images)


def _pdf(data: bytes) -> ExtractedDocument:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    images: list[ReportImage] = []
    seen: set[str] = set()
    for page in reader.pages:
        parts.append(_clean(page.extract_text()))
        try:
            page_images = list(page.images)
        except Exception:  # нестандартное кодирование изображения
            page_images = []
        for img in page_images:
            blob = img.data
            h = hashlib.sha256(blob).hexdigest()
            if h in seen or PurePosixPath(img.name).suffix.lower() not in _RASTER | {".jp2"}:
                continue
            seen.add(h)
            images.append(ReportImage(len(images) + 1, blob, img.name))
            parts.append(f" {MARKER.format(len(images))} ")
        parts.append("\n")
    return ExtractedDocument(normalize_whitespace("\n".join(parts)), images)


async def fetch_google_doc(url: str, timeout: float = 30.0) -> ExtractedDocument:
    """Загружает открытый по ссылке документ Google Docs вместе с рисунками (экспорт в DOCX)."""
    import aiohttp

    from .text_extraction import google_doc_id

    doc_id = google_doc_id(url)
    if not doc_id:
        raise ExtractionError("Ссылка не похожа на документ Google Docs (…/document/d/<id>/…).")
    export = f"https://docs.google.com/document/d/{doc_id}/export?format=docx"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async with session.get(export, allow_redirects=True) as resp:
            body = await resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if resp.status != 200 or "text/html" in ctype:
                raise ExtractionError(
                    "Документ недоступен. Откройте доступ «Все, у кого есть ссылка» "
                    "или загрузите отчёт файлом.")
    return extract_document(body, "gdoc.docx")


# ── Обезличивание перед отправкой во внешние модели ────────────────────────────
_TITLE_END = re.compile(r"^\s*(г\.\s*)?Минск[,.]?\s*(20\d\d)?\s*(г\.?)?\s*$|^\s*20\d\d\s*(г\.?)?\s*$", re.IGNORECASE)
_TITLE_HINT = re.compile(r"Выполнил|Проверил|Министерство|Учреждение образования|университет|"
                         r"студент\w*\s+гр|Группа|Кафедра", re.IGNORECASE)
_PERSONAL_LINE = re.compile(r"^\s*(Выполнил\w*|Проверил\w*)\b.*$",
                            re.IGNORECASE | re.MULTILINE)


def strip_title_page(text: str, scan_lines: int = 60) -> str:
    """Удаляет титульный лист (до строки «Минск 2026» или года) и строки
    «Выполнил…/Проверил…»: ФИО, группа и преподаватель не передаются внешним моделям.

    Титульный лист распознаётся, только если в отрезанной части есть его признаки
    («Выполнил», «Министерство», «Кафедра» и т. п.) — обычный текст не страдает.
    Маркеры рисунков с титульного листа (логотип) удаляются вместе с ним.
    """
    lines = (text or "").split("\n")
    for i, line in enumerate(lines[:scan_lines]):
        if _TITLE_END.match(MARKER_RE.sub("", line)) and _TITLE_HINT.search("\n".join(lines[:i])):
            lines = lines[i + 1:]
            break
    return _PERSONAL_LINE.sub("", "\n".join(lines)).strip()


# ── Подписи рисунков ──────────────────────────────────────────────────────────
_CAPTION = re.compile(r"^\s*(Рис\.?|Рисунок)\s*\d", re.IGNORECASE)
_RESULT_WORDS = re.compile(r"результат|демонстрац|работ[аы] программ|пример работы|вывод программ|"
                           r"тестирован|окн[оа]|интерфейс|запуск|построени|скриншот|снимок экрана", re.IGNORECASE)


def image_captions(text: str) -> dict[int, str]:
    """Подпись каждого рисунка: строка «Рисунок N — …» в пределах двух строк после маркера."""
    lines = (text or "").split("\n")
    out: dict[int, str] = {}
    for i, line in enumerate(lines):
        for m in MARKER_RE.finditer(line):
            tail = MARKER_RE.sub("", line[m.end():]).strip()
            near = ([tail] if tail else []) + [MARKER_RE.sub("", x).strip() for x in lines[i + 1:i + 3]]
            cap = next((x for x in near if _CAPTION.match(x)), "")
            out[int(m.group(1))] = cap[:200]
    return out


def image_priority(caption: str) -> int:
    """2 — подпись говорит о результате работы, 1 — есть подпись, 0 — подписи нет."""
    if not caption:
        return 0
    return 2 if _RESULT_WORDS.search(caption) else 1
