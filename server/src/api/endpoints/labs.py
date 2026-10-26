from fastapi import Depends, HTTPException

from auth import CurrentUser, ensure_course_access, ensure_course_owner, get_current_user, require_teacher
from database.sql import LabRepository
from models.lab import NewLab

from ..app import app


def _lab_dict(row) -> dict:
    lab_id, number, title, task, *rest = row
    data = {"id": lab_id, "number": number, "title": title, "task": task}
    if len(rest) == 3:
        data["course_id"], data["min_words"], data["required_sections"] = rest
    else:
        data["min_words"], data["required_sections"] = rest
    return data


@app.get("/api/v1/courses/{course_id}/labs", tags=["Лабораторные"])
def get_labs(course_id: int, user: CurrentUser = Depends(get_current_user)):
    ensure_course_access(user, course_id)
    return [_lab_dict(r) for r in LabRepository().get_labs(course_id)]


@app.post("/api/v1/courses/{course_id}/labs", tags=["Лабораторные"])
def create_lab(course_id: int, payload: NewLab, user: CurrentUser = Depends(require_teacher)):
    ensure_course_owner(user, course_id)
    lab_id = LabRepository().create(payload, course_id)
    return {"success": True, "id": lab_id}


def _lab_for_owner(lab_id: int, user: CurrentUser) -> dict:
    row = LabRepository().get_by_id(lab_id)
    if not row:
        raise HTTPException(404, "Лабораторная не найдена")
    lab = _lab_dict(row)
    ensure_course_owner(user, lab["course_id"])
    return lab


@app.get("/api/v1/labs/{lab_id}", tags=["Лабораторные"])
def get_lab(lab_id: int, user: CurrentUser = Depends(get_current_user)):
    row = LabRepository().get_by_id(lab_id)
    if not row:
        raise HTTPException(404, "Лабораторная не найдена")
    lab = _lab_dict(row)
    ensure_course_access(user, lab["course_id"])
    return lab


@app.put("/api/v1/labs/{lab_id}", tags=["Лабораторные"])
def update_lab(lab_id: int, payload: NewLab, user: CurrentUser = Depends(require_teacher)):
    _lab_for_owner(lab_id, user)
    LabRepository().update(lab_id, number=payload.number, title=payload.title, task=payload.task,
                           min_words=payload.min_words, required_sections=payload.required_sections)
    return {"success": True}


@app.delete("/api/v1/labs/{lab_id}", tags=["Лабораторные"])
def delete_lab(lab_id: int, user: CurrentUser = Depends(require_teacher)):
    _lab_for_owner(lab_id, user)
    LabRepository().delete(lab_id)
    return {"success": True}
