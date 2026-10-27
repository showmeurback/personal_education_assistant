"""Приём отчётов по лабораторным работам и запуск гибридной проверки."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg2.errors

from agents.verification.pipeline import VerificationPipeline, VerificationResult
from agents.verification.rules import LabRequirements
from common.documents import ExtractedDocument, extract_document, fetch_google_doc
from database.sql.repositories.labs import LabRepository
from database.sql.repositories.reports import ReportRepository
from database.vector.repositories.report_index import ReportIndex
from log import logger
from models.enums import ReportStatus, VerificationDecision
from settings import settings, verification_settings

MAX_FILE_BYTES = 15 * 1024 * 1024

_STATUS_BY_DECISION = {
    VerificationDecision.APPROVE: ReportStatus.PENDING,
    VerificationDecision.REJECT: ReportStatus.AI_REJECTED,
    VerificationDecision.MANUAL_REVIEW: ReportStatus.MANUAL_REVIEW,
}


class ReportSubmissionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class SubmissionInput:
    student_id: int
    lab_id: int
    url: str | None = None
    file_bytes: bytes | None = None
    filename: str | None = None


def student_view_protocol(protocol: list[dict]) -> list[dict]:
    """Протокол для студента: без идентификаторов чужих отчётов и служебных данных."""
    out = []
    for step in protocol:
        step = {**step, "details": dict(step.get("details") or {})}
        nearest = step["details"].get("nearest")
        if isinstance(nearest, dict):
            step["details"]["nearest"] = {"similarity": nearest.get("similarity"),
                                          "hamming": nearest.get("hamming")}
        step["details"].pop("fingerprint_hex", None)
        out.append(step)
    return out


class ReportService:
    """Приём отчёта и гибридная проверка в фоне.

    Отправка отчёта только сохраняет его со статусом «проверяется» и возвращает ответ
    сразу; сама проверка выполняется фоновой задачей (не более VERIFICATION_CONCURRENCY
    одновременно, остальные ждут в очереди), а клиент узнаёт результат опросом.
    Так массовая сдача не упирается в тайм-ауты HTTP, а уникальный индекс в БД не даёт
    создать два активных отчёта одновременными запросами.
    """

    def __init__(self, pipeline: VerificationPipeline | None = None) -> None:
        self.index = ReportIndex()
        self.pipeline = pipeline or VerificationPipeline(self.index, mode="hybrid")
        self.reports = ReportRepository()
        self.labs = LabRepository()
        self._tasks: set[asyncio.Task] = set()
        self._slots: asyncio.Semaphore | None = None

    def _semaphore(self) -> asyncio.Semaphore:
        if self._slots is None:
            self._slots = asyncio.Semaphore(max(1, verification_settings.check_concurrency))
        return self._slots

    async def submit(self, data: SubmissionInput, wait: bool = False) -> dict:
        lab = await asyncio.to_thread(self.labs.get_by_id, data.lab_id)
        if not lab:
            raise ReportSubmissionError("Лабораторная работа не найдена", 404)
        _id, _num, _title, task, course_id, min_words, required_sections = lab

        blocking = await asyncio.to_thread(self.reports.has_active_report, data.student_id, data.lab_id)
        self._raise_if_blocking(blocking)

        source_type, file_path, filename = "gdoc", None, None
        if data.file_bytes is not None:
            if len(data.file_bytes) > MAX_FILE_BYTES:
                raise ReportSubmissionError("Файл больше 15 МБ")
            # разбор DOCX/PDF — вычисления на процессоре: в отдельном потоке
            doc = await asyncio.to_thread(extract_document, data.file_bytes, data.filename or "report")
            source_type, filename = "file", Path(data.filename or "report").name
        elif data.url:
            doc = await fetch_google_doc(data.url)
        else:
            raise ReportSubmissionError("Загрузите файл отчёта или укажите ссылку на Google Docs")

        if data.file_bytes is not None:
            file_path = await asyncio.to_thread(self._save_file, data.file_bytes, filename)
        try:
            report_id = await asyncio.to_thread(
                self.reports.create, student_id=data.student_id, lab_id=data.lab_id, source_type=source_type,
                url=data.url, filename=filename, file_path=file_path, text=doc.plain,  # без маркеров рисунков
                status=ReportStatus.CHECKING, ai_summary=None)
        except psycopg2.errors.UniqueViolation:
            # одновременный второй запрос (двойной клик): первый уже создал активный отчёт
            if file_path:
                Path(file_path).unlink(missing_ok=True)
            raise ReportSubmissionError("Отчёт по этой лабораторной уже отправлен и проверяется", 409)

        requirements = await asyncio.to_thread(self._requirements, course_id, data.lab_id, task, min_words,
                                               required_sections)
        task_ = asyncio.create_task(self._check(report_id, data.student_id, data.lab_id, doc, requirements))
        self._tasks.add(task_)
        task_.add_done_callback(self._tasks.discard)
        if wait:  # синхронный режим (сценарии, скрипты): дождаться результата проверки
            return await task_
        return {"report_id": report_id, "status": ReportStatus.CHECKING.value,
                "message": "Отчёт принят и проверяется. Результат появится через несколько секунд."}

    @staticmethod
    def _raise_if_blocking(blocking: str | None) -> None:
        if blocking == ReportStatus.APPROVED.value:
            raise ReportSubmissionError("Отчёт по этой лабораторной уже принят", 409)
        if blocking == ReportStatus.CHECKING.value:
            raise ReportSubmissionError("Отчёт по этой лабораторной уже отправлен и проверяется", 409)
        if blocking:
            raise ReportSubmissionError("Предыдущий отчёт ещё на проверке у преподавателя", 409)

    def _requirements(self, course_id: int, lab_id: int, task, min_words, required_sections) -> LabRequirements:
        req = LabRequirements.from_db(task, min_words, required_sections)
        req.other_tasks = [row[3] for row in self.labs.get_labs(course_id) if row[0] != lab_id and row[3]]
        return req

    async def _check(self, report_id: int, student_id: int, lab_id: int, doc: ExtractedDocument,
                     requirements: LabRequirements) -> dict:
        async with self._semaphore():
            try:
                # общий предел времени: даже при зависшем внешнем сервисе отчёт не остаётся «проверяется»
                result: VerificationResult = await asyncio.wait_for(self.pipeline.run(
                    text=doc.text, images=doc.images, requirements=requirements,
                    student_id=student_id, lab_id=lab_id), timeout=verification_settings.check_timeout)
            except Exception as exc:  # отчёт не должен «зависнуть» в статусе «проверяется»
                timed_out = isinstance(exc, (asyncio.TimeoutError, TimeoutError))
                if timed_out:
                    logger.warning(f"Проверка отчёта {report_id} не уложилась в {verification_settings.check_timeout:.0f} с")
                else:
                    logger.exception(f"Проверка отчёта {report_id} не завершилась: {exc}")
                message = (f"Сервисы языковых моделей не ответили за {verification_settings.check_timeout / 60:.0f} мин. "
                           "Отчёт передан преподавателю для ручной проверки." if timed_out else
                           "Автоматическая проверка не завершилась из-за внутренней ошибки. "
                           "Отчёт передан преподавателю для ручной проверки.")
                await asyncio.to_thread(self.reports.finish_check, report_id, ReportStatus.MANUAL_REVIEW, message)
                await asyncio.to_thread(
                    self.reports.add_check, report_id=report_id, decision="manual_review", decided_by="error",
                    final_score=None, max_similarity=None, llm_calls=0, duration_ms=0,
                    protocol=[{"order": 1, "step": 1, "title": "Сбой проверки", "component": "Сервис проверки",
                               "kind": "symbolic", "status": "fail", "duration_ms": 0,
                               "details": {"error": "Превышено время проверки" if timed_out else type(exc).__name__}}])
                return {"report_id": report_id, "status": ReportStatus.MANUAL_REVIEW.value,
                        "decision": "manual_review", "decided_by": "error", "reason": "Сбой проверки",
                        "message": message, "score": None, "llm_calls": 0, "vision_calls": 0,
                        "duration_ms": 0, "protocol": []}
        status = _STATUS_BY_DECISION[result.decision]
        await asyncio.to_thread(self.reports.finish_check, report_id, status, result.feedback)
        await asyncio.to_thread(
            self.reports.add_check, report_id=report_id, decision=result.decision.value,
            decided_by=result.decided_by, final_score=result.score, max_similarity=result.max_similarity,
            llm_calls=result.llm_calls, duration_ms=result.duration_ms, protocol=result.protocol)
        # отпечаток сохраняется для всех отчётов, кроме признанных заимствованием
        if result.fingerprint and result.decided_by not in ("simhash", "rules"):
            try:
                await asyncio.to_thread(self.index.add, result.fingerprint, report_id=report_id,
                                        student_id=student_id, lab_id=lab_id)
            except Exception as exc:
                logger.error(f"Не удалось сохранить отпечаток отчёта {report_id}: {exc}")
        return {
            "report_id": report_id,
            "status": status.value,
            "decision": result.decision.value,
            "decided_by": result.decided_by,
            "reason": result.reason,
            "message": result.feedback,
            "score": result.score,
            "llm_calls": result.llm_calls,
            "vision_calls": result.vision_calls,
            "duration_ms": result.duration_ms,
            "protocol": student_view_protocol(result.protocol),
        }

    async def resume_interrupted(self) -> int:
        """Повторно запускает проверки, прерванные перезапуском сервера."""
        rows = await asyncio.to_thread(self.reports.list_checking)
        for report_id, student_id, lab_id, file_path, filename, url, text in rows:
            try:
                lab = await asyncio.to_thread(self.labs.get_by_id, lab_id)
                if file_path and Path(file_path).exists():
                    doc = await asyncio.to_thread(extract_document, Path(file_path).read_bytes(), filename or file_path)
                else:  # ссылка Google Docs: проверяется сохранённый текст (без рисунков)
                    doc = ExtractedDocument(text or "")
                _id, _n, _t, task, course_id, min_words, sections = lab
                req = await asyncio.to_thread(self._requirements, course_id, lab_id, task, min_words, sections)
            except Exception as exc:
                logger.error(f"Не удалось возобновить проверку отчёта {report_id}: {exc}")
                continue
            t = asyncio.create_task(self._check(report_id, student_id, lab_id, doc, req))
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)
        if rows:
            logger.info(f"Возобновлено прерванных проверок: {len(rows)}")
        return len(rows)

    @staticmethod
    def _save_file(data: bytes, filename: str) -> str:
        folder = Path(settings.uploads_dir) / "reports"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
        path.write_bytes(data)
        return str(path)
