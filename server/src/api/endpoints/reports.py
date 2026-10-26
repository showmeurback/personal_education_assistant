from fastapi import Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from auth import CurrentUser, ensure_course_access, get_current_user, require_student, require_teacher
from database.sql import LabRepository
from database.sql.repositories.reports import ReportRepository
from models.enums import ReportStatus
from services.report_service import (ReportService, ReportSubmissionError, SubmissionInput,
                                     student_view_protocol)

from ..app import app

_service: ReportService | None = None


def _get_service() -> ReportService:
    global _service
    if _service is None:
        _service = ReportService()
    return _service


@app.on_event("startup")
async def _resume_interrupted_checks() -> None:
    """Проверки, прерванные перезапуском сервера, запускаются заново."""
    try:
        await _get_service().resume_interrupted()
    except Exception as exc:  # БД ещё недоступна и т. п. — сервер всё равно запускается
        from log import logger
        logger.error(f"Не удалось возобновить прерванные проверки: {exc}")


@app.post("/api/v1/labs/{lab_id}/reports", tags=["Отчёты"], status_code=202)
async def submit_report(
    lab_id: int,
    url: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    wait: bool = Query(default=False, description="дождаться результата проверки в этом же запросе"),
    user: CurrentUser = Depends(require_student),
):
    """Сдача отчёта: файл (PDF/DOCX/TXT) или ссылка на Google Docs.

    По умолчанию отчёт сохраняется со статусом «checking» и сразу возвращается ответ 202;
    гибридная проверка выполняется в фоне, результат — в GET /reports/{id} и
    GET /labs/{id}/my-reports. С параметром wait=true ответ 200 содержит решение и протокол.
    """
    lab = LabRepository().get_by_id(lab_id)
    if not lab:
        raise HTTPException(404, "Лабораторная не найдена")
    ensure_course_access(user, lab[4])
    data = SubmissionInput(student_id=user.id, lab_id=lab_id, url=(url or "").strip() or None)
    if file is not None and file.filename:
        data.file_bytes = await file.read()
        data.filename = file.filename
    try:
        result = await _get_service().submit(data, wait=wait)
    except ReportSubmissionError as exc:
        raise HTTPException(exc.status_code, str(exc))
    return JSONResponse(result, status_code=200 if wait else 202)


@app.get("/api/v1/labs/{lab_id}/my-reports", tags=["Отчёты"])
def my_lab_reports(lab_id: int, user: CurrentUser = Depends(require_student)):
    repo = ReportRepository()
    reports = repo.get_student_lab_reports(user.id, lab_id)
    for r in reports:
        check = repo.get_check(r["report_id"])
        r["check"] = None if check is None else {
            **{k: v for k, v in check.items() if k != "protocol"},
            "protocol": student_view_protocol(check["protocol"]),
        }
    return {"reports": reports}


def _report_for_viewer(report_id: int, user: CurrentUser) -> dict:
    report = ReportRepository().get_by_id(report_id)
    if not report:
        raise HTTPException(404, "Отчёт не найден")
    if user.is_student and report["student_id"] == user.id:
        return report
    if user.is_teacher and report["teacher_id"] == user.id:
        return report
    raise HTTPException(403, "Нет доступа к отчёту")


@app.get("/api/v1/reports/{report_id}", tags=["Отчёты"])
def get_report(report_id: int, user: CurrentUser = Depends(get_current_user)):
    """Отчёт с протоколом гибридной проверки (для преподавателя — полный протокол)."""
    report = _report_for_viewer(report_id, user)
    check = ReportRepository().get_check(report_id)
    if check and user.is_student:
        check["protocol"] = student_view_protocol(check["protocol"])
    report.pop("teacher_id", None)
    if user.is_student:
        report.pop("text", None)
    return {"report": report, "check": check}


@app.get("/api/v1/reports/{report_id}/file", tags=["Отчёты"])
def download_report_file(report_id: int, user: CurrentUser = Depends(get_current_user)):
    _report_for_viewer(report_id, user)
    path, filename = ReportRepository().get_file_path(report_id)
    if not path:
        raise HTTPException(404, "Отчёт сдан ссылкой, файла нет")
    return FileResponse(path, filename=filename or "report", media_type="application/octet-stream")


class StatusModel(BaseModel):
    status: str
    comment: str | None = Field(default=None, max_length=3000)


@app.post("/api/v1/reports/{report_id}/status", tags=["Отчёты"])
def set_report_status(report_id: int, payload: StatusModel, user: CurrentUser = Depends(require_teacher)):
    _report_for_viewer(report_id, user)
    mapping = {"approved": ReportStatus.APPROVED, "not-approved": ReportStatus.NOT_APPROVED}
    status = mapping.get(payload.status.strip().lower())
    if status is None:
        raise HTTPException(400, "Допустимые статусы: approved, not-approved")
    ReportRepository().set_report_status(report_id, status, (payload.comment or "").strip() or None)
    return {"success": True}
