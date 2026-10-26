"""Извлечение текста из файлов (PDF, DOCX, TXT) и документов Google Docs."""
from __future__ import annotations

import io
import re
from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class UnsupportedFileError(ValueError):
    pass


class ExtractionError(ValueError):
    pass


# Защита от «zip-бомб»: DOCX — это zip-архив, и файл в несколько мегабайт может
# распаковываться в гигабайты. Размеры проверяются по заголовкам архива до распаковки.
MAX_DOCX_MEMBER_BYTES = 40 * 1024 * 1024      # один элемент архива (document.xml, рисунок)
MAX_DOCX_TOTAL_BYTES = 200 * 1024 * 1024      # сумма распакованных элементов
MAX_DOCX_MEMBERS = 3000


def check_zip_limits(data: bytes, filename: str = "документ") -> None:
    import zipfile

    try:
        infos = zipfile.ZipFile(io.BytesIO(data)).infolist()
    except zipfile.BadZipFile as exc:
        raise ExtractionError(f"Файл «{filename}» повреждён или не является документом DOCX") from exc
    if len(infos) > MAX_DOCX_MEMBERS:
        raise ExtractionError(f"Файл «{filename}» содержит слишком много элементов")
    total = 0
    for info in infos:
        if info.file_size > MAX_DOCX_MEMBER_BYTES:
            raise ExtractionError(
                f"Файл «{filename}» содержит слишком большой элемент ({info.filename}, "
                f"{info.file_size // 2**20} МБ после распаковки)")
        total += info.file_size
    if total > MAX_DOCX_TOTAL_BYTES:
        raise ExtractionError(f"Файл «{filename}» после распаковки превышает {MAX_DOCX_TOTAL_BYTES // 2**20} МБ")


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"Формат файла «{filename}» не поддерживается. Допустимы: PDF, DOCX, TXT."
        )
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        elif ext == ".docx":
            check_zip_limits(data, filename)
            text = _docx_text(data)
        else:
            text = _decode_text(data)
    except (UnsupportedFileError, ExtractionError):
        raise
    except Exception as exc:  # повреждённый файл
        raise ExtractionError(f"Не удалось прочитать файл «{filename}»: {exc}") from exc
    return normalize_whitespace(text)


def extract_text_from_path(path: str | Path) -> str:
    p = Path(path)
    return extract_text_from_bytes(p.read_bytes(), p.name)


def _docx_text(data: bytes) -> str:
    import docx2txt
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return docx2txt.process(tmp_path) or ""
    finally:
        os.unlink(tmp_path)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "cp1251", "koi8-r"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


_GDOC_RE = re.compile(r"docs\.google\.com/document/(?:u/\d+/)?d/([a-zA-Z0-9_-]{10,})")


def google_doc_id(url: str) -> str | None:
    match = _GDOC_RE.search(url or "")
    return match.group(1) if match else None


async def fetch_google_doc_text(url: str, timeout: float = 20.0) -> str:
    """Загружает текст открытого по ссылке документа Google Docs (экспорт в text/plain)."""
    import aiohttp

    doc_id = google_doc_id(url)
    if not doc_id:
        raise ExtractionError("Ссылка не похожа на документ Google Docs (…/document/d/<id>/…).")
    export = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async with session.get(export, allow_redirects=True) as resp:
            body = await resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if resp.status != 200 or "text/html" in ctype:
                raise ExtractionError(
                    "Документ недоступен. Откройте доступ «Все, у кого есть ссылка» "
                    "или загрузите отчёт файлом."
                )
    return normalize_whitespace(_decode_text(body))
