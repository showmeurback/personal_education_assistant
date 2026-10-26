from pathlib import Path
from typing import List

from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from auth import CurrentUser, ensure_course_access, ensure_course_owner, get_current_user, require_teacher
from common.text_extraction import SUPPORTED_EXTENSIONS
from database.sql import CourseRepository
from database.vector.repositories import StorageManager
from rag.indexer import Indexer
from settings import settings

from ..app import app

MAX_FILE_BYTES = 30 * 1024 * 1024


def _uploads_dir() -> Path:
    path = Path(settings.uploads_dir) / "materials"
    path.mkdir(parents=True, exist_ok=True)
    return path


@app.post("/api/v1/courses/{course_id}/files", tags=["Курсы"])
async def upload_course_files(course_id: int, files: List[UploadFile] = File(...),
                              user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    repo = CourseRepository()
    storage_id = repo.get_storage_id(course_id)
    if not storage_id or not StorageManager.exists(storage_id):
        storage_id = StorageManager.create_storage()
        repo.update(course_id, storage_id=storage_id)
    indexer = Indexer(storage_id)

    indexed, errors = [], []
    for file in files:
        name = Path(file.filename or "file").name
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            errors.append({"filename": name, "error": "Неподдерживаемый формат (нужен PDF, DOCX или TXT)"})
            continue
        data = await file.read()
        if len(data) > MAX_FILE_BYTES:
            errors.append({"filename": name, "error": "Файл больше 30 МБ"})
            continue
        try:
            file_id, chunks = indexer.add_file(data, name)
        except ValueError as exc:
            errors.append({"filename": name, "error": str(exc)})
            continue
        (_uploads_dir() / f"{file_id}{suffix}").write_bytes(data)
        repo.add_course_file(course_id, name, file_id)
        indexed.append({"filename": name, "file_id": file_id, "chunks": chunks})
    if not indexed and errors:
        raise HTTPException(400, "; ".join(f"{e['filename']}: {e['error']}" for e in errors))
    return {"success": True, "indexed": indexed, "errors": errors}


@app.get("/api/v1/courses/{course_id}/files", tags=["Курсы"])
def list_course_files(course_id: int, user: CurrentUser = Depends(get_current_user)):
    ensure_course_access(user, course_id)
    rows = CourseRepository().get_course_files(course_id)
    return {"files": [{"id": r[0], "filename": r[1], "file_id": r[2], "created_at": str(r[3])} for r in rows]}


@app.delete("/api/v1/courses/{course_id}/files/{file_record_id}", tags=["Курсы"])
def delete_course_file(course_id: int, file_record_id: int, user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    repo = CourseRepository()
    row = next((r for r in repo.get_course_files(course_id) if r[0] == file_record_id), None)
    if not row:
        raise HTTPException(404, "Файл не найден")
    file_id = row[2]
    storage_id = repo.get_storage_id(course_id)
    if storage_id and StorageManager.exists(storage_id):
        StorageManager.get_vector_storage(storage_id).delete_by_file_id(file_id)
    for path in _uploads_dir().glob(f"{file_id}.*"):
        path.unlink(missing_ok=True)
    repo.delete_course_file(file_record_id)
    return {"success": True}


@app.get("/api/v1/courses/{course_id}/files/{file_id}/download", tags=["Курсы"])
def download_course_file(course_id: int, file_id: str, user: CurrentUser = Depends(get_current_user)):
    ensure_course_access(user, course_id)
    row = next((r for r in CourseRepository().get_course_files(course_id) if r[2] == file_id), None)
    if not row:
        raise HTTPException(404, "Файл не найден")
    matches = list(_uploads_dir().glob(f"{file_id}.*"))
    if not matches:
        raise HTTPException(404, "Файл отсутствует на диске")
    return FileResponse(matches[0], filename=row[1], media_type="application/octet-stream")
