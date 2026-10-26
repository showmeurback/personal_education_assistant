import json

from psycopg2.extensions import cursor

from settings import EducationDatabaseConfig
from ..connection import postgre_connection
from models.enums import ReportStatus

_REPORT_FIELDS = """
    r.id, r.student_id, s.first_name, s.last_name, c.id, c.title, l.id, l.number, l.title,
    r.url, r.source_type, r.filename, r.status, r.comment, r.ai_summary, r.created_at::text
"""


def _row_to_dict(row) -> dict:
    (rid, sid, first, last, cid, ctitle, lid, lnum, ltitle,
     url, source, filename, status, comment, ai_summary, created_at) = row
    return {
        "report_id": rid,
        "student_id": sid,
        "student_name": f"{last} {first}",
        "course_id": cid,
        "course_title": ctitle,
        "lab_id": lid,
        "lab_number": lnum,
        "lab_title": ltitle,
        "url": url,
        "source_type": source,
        "filename": filename,
        "status": status,
        "comment": comment,
        "ai_summary": ai_summary,
        "created_at": created_at,
    }


_BASE_JOIN = """
    FROM reports r
    JOIN labs l ON l.id = r.lab_id
    JOIN courses c ON c.id = l.course_id
    JOIN students s ON s.id = r.student_id
"""


class ReportRepository:
    __config = EducationDatabaseConfig()

    @postgre_connection(__config)
    def create(
        self,
        *,
        student_id: int,
        lab_id: int,
        source_type: str,
        url: str | None,
        filename: str | None,
        file_path: str | None,
        text: str,
        status: ReportStatus,
        ai_summary: str | None,
        curs: cursor = None,
    ) -> int:
        curs.execute(
            """
            INSERT INTO reports (lab_id, student_id, url, source_type, filename, file_path,
                                 text, status, ai_summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (lab_id, student_id, url, source_type, filename, file_path, text,
             status.value, ai_summary),
        )
        return curs.fetchone()[0]

    @postgre_connection(__config)
    def finish_check(self, report_id: int, status: ReportStatus, ai_summary: str | None,
                     curs: cursor = None) -> None:
        """Итог автоматической проверки: статус меняется, только если отчёт ещё «проверяется»."""
        curs.execute("UPDATE reports SET status = %s, ai_summary = %s WHERE id = %s AND status = 'checking'",
                     (status.value, ai_summary, report_id))

    @postgre_connection(__config)
    def list_checking(self, curs: cursor = None) -> list[tuple]:
        """Отчёты, проверка которых была прервана (например, перезапуском сервера)."""
        curs.execute("""
            SELECT r.id, r.student_id, r.lab_id, r.file_path, r.filename, r.url, r.text
            FROM reports r WHERE r.status = 'checking' ORDER BY r.created_at
        """)
        return curs.fetchall()

    @postgre_connection(__config)
    def add_check(
        self,
        *,
        report_id: int,
        decision: str,
        decided_by: str,
        final_score: float | None,
        max_similarity: float | None,
        llm_calls: int,
        duration_ms: int,
        protocol: list[dict],
        curs: cursor = None,
    ) -> int:
        curs.execute(
            """
            INSERT INTO report_checks (report_id, decision, decided_by, final_score,
                                       max_similarity, llm_calls, duration_ms, protocol)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (report_id, decision, decided_by, final_score, max_similarity, llm_calls,
             duration_ms, json.dumps(protocol, ensure_ascii=False)),
        )
        return curs.fetchone()[0]

    @postgre_connection(__config)
    def get_check(self, report_id: int, curs: cursor = None) -> dict | None:
        curs.execute(
            """
            SELECT decision, decided_by, final_score, max_similarity, llm_calls, duration_ms,
                   protocol, created_at::text
            FROM report_checks WHERE report_id = %s ORDER BY id DESC LIMIT 1
            """,
            (report_id,),
        )
        row = curs.fetchone()
        if not row:
            return None
        protocol = row[6] if isinstance(row[6], list) else json.loads(row[6])
        return {
            "decision": row[0], "decided_by": row[1], "final_score": row[2],
            "max_similarity": row[3], "llm_calls": row[4], "duration_ms": row[5],
            "protocol": protocol, "created_at": row[7],
        }

    @postgre_connection(__config)
    def get_by_id(self, report_id: int, curs: cursor = None) -> dict | None:
        curs.execute(f"SELECT {_REPORT_FIELDS}, c.teacher_id, r.text {_BASE_JOIN} WHERE r.id = %s",
                     (report_id,))
        row = curs.fetchone()
        if not row:
            return None
        data = _row_to_dict(row[:16])
        data["teacher_id"] = row[16]
        data["text"] = row[17]
        return data

    @postgre_connection(__config)
    def get_file_path(self, report_id: int, curs: cursor = None) -> tuple[str | None, str | None]:
        curs.execute("SELECT file_path, filename FROM reports WHERE id = %s", (report_id,))
        row = curs.fetchone()
        return (row[0], row[1]) if row else (None, None)

    @postgre_connection(__config)
    def get_teacher_queue(self, teacher_id: int, curs: cursor = None) -> list[dict]:
        """Отчёты, ожидающие решения преподавателя: прошедшие проверку и требующие ручной проверки."""
        curs.execute(
            f"""
            SELECT {_REPORT_FIELDS} {_BASE_JOIN}
            WHERE c.teacher_id = %s AND r.status IN ('pending', 'manual-review')
            ORDER BY (r.status = 'manual-review') DESC, r.created_at
            """,
            (teacher_id,),
        )
        return [_row_to_dict(r) for r in curs.fetchall()]

    @postgre_connection(__config)
    def get_teacher_history(self, teacher_id: int, limit: int = 100, curs: cursor = None) -> list[dict]:
        curs.execute(
            f"""
            SELECT {_REPORT_FIELDS} {_BASE_JOIN}
            WHERE c.teacher_id = %s ORDER BY r.created_at DESC LIMIT %s
            """,
            (teacher_id, limit),
        )
        return [_row_to_dict(r) for r in curs.fetchall()]

    @postgre_connection(__config)
    def set_report_status(self, report_id: int, status: ReportStatus, comment: str | None = None,
                          curs: cursor = None) -> bool:
        curs.execute(
            "UPDATE reports SET status = %s, comment = %s WHERE id = %s RETURNING id",
            (status.value, comment, report_id),
        )
        return curs.fetchone() is not None

    @postgre_connection(__config)
    def get_student_reports(self, student_id: int, curs: cursor = None) -> list[dict]:
        curs.execute(
            f"SELECT {_REPORT_FIELDS} {_BASE_JOIN} WHERE r.student_id = %s ORDER BY r.created_at DESC",
            (student_id,),
        )
        return [_row_to_dict(r) for r in curs.fetchall()]

    @postgre_connection(__config)
    def get_student_lab_reports(self, student_id: int, lab_id: int, curs: cursor = None) -> list[dict]:
        curs.execute(
            f"""SELECT {_REPORT_FIELDS} {_BASE_JOIN}
                WHERE r.student_id = %s AND r.lab_id = %s ORDER BY r.created_at DESC""",
            (student_id, lab_id),
        )
        return [_row_to_dict(r) for r in curs.fetchall()]

    @postgre_connection(__config)
    def has_active_report(self, student_id: int, lab_id: int, curs: cursor = None) -> str | None:
        """Статус отчёта, блокирующего повторную отправку (на проверке или уже принят)."""
        curs.execute(
            """
            SELECT status FROM reports
            WHERE student_id = %s AND lab_id = %s
              AND status IN ('pending', 'manual-review', 'approved')
            ORDER BY created_at DESC LIMIT 1
            """,
            (student_id, lab_id),
        )
        row = curs.fetchone()
        return row[0] if row else None

    @postgre_connection(__config)
    def get_by_student_and_course(self, student_id: int, course_id: int, curs: cursor = None) -> list[tuple]:
        query = """
            SELECT r.id, c.title, l.title, r.url, r.status, r.comment
            FROM reports AS r
            JOIN labs AS l ON r.lab_id = l.id
            JOIN courses AS c ON l.course_id = c.id
            WHERE r.student_id = %s AND c.id = %s
            ORDER BY r.created_at DESC
            """
        curs.execute(query, (student_id, course_id))
        return curs.fetchall()

    @postgre_connection(__config)
    def get_course_report_analytics(self, course_id: int, curs: cursor = None) -> list[tuple]:
        query = """
            SELECT DISTINCT ON (r.student_id, l.id)
                   r.student_id, s.first_name, s.last_name, l.title AS lab_title, r.status
            FROM reports r
            JOIN labs l ON r.lab_id = l.id
            JOIN students s ON s.id = r.student_id
            WHERE l.course_id = %s
            ORDER BY r.student_id, l.id, r.created_at DESC
            """
        curs.execute(query, (course_id,))
        return curs.fetchall()

    @postgre_connection(__config)
    def get_lab_funnel(self, course_id: int, curs: cursor = None) -> list[tuple]:
        """Воронка сдачи лаб по последней попытке каждого студента:
        (id, number, title, enrolled, submitted, approved, rejected)."""
        query = """
            WITH last_reports AS (
                SELECT DISTINCT ON (r.student_id, r.lab_id) r.student_id, r.lab_id, r.status
                FROM reports r
                JOIN labs l ON l.id = r.lab_id
                WHERE l.course_id = %(cid)s
                ORDER BY r.student_id, r.lab_id, r.created_at DESC
            )
            SELECT l.id, l.number, l.title,
                   (SELECT COUNT(*) FROM students_courses sc WHERE sc.course_id = %(cid)s) AS enrolled,
                   COUNT(lr.student_id)                                              AS submitted,
                   COUNT(lr.student_id) FILTER (WHERE lr.status = 'approved')        AS approved,
                   COUNT(lr.student_id) FILTER (WHERE lr.status IN ('not-approved', 'ai-rejected')) AS rejected
            FROM labs l
            LEFT JOIN last_reports lr ON lr.lab_id = l.id
            WHERE l.course_id = %(cid)s
            GROUP BY l.id, l.number, l.title
            ORDER BY l.number
        """
        curs.execute(query, {"cid": course_id})
        return curs.fetchall()

    @postgre_connection(__config)
    def get_verification_stats(self, course_id: int | None = None, teacher_id: int | None = None,
                               curs: cursor = None) -> list[tuple]:
        """Статистика автоматических решений: (decision, decided_by, count, avg_ms, avg_llm_calls)."""
        where, params = [], []
        if course_id is not None:
            where.append("l.course_id = %s")
            params.append(course_id)
        if teacher_id is not None:
            where.append("c.teacher_id = %s")
            params.append(teacher_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        curs.execute(
            f"""
            SELECT rc.decision, rc.decided_by, COUNT(*), AVG(rc.duration_ms), AVG(rc.llm_calls)
            FROM report_checks rc
            JOIN reports r ON r.id = rc.report_id
            JOIN labs l ON l.id = r.lab_id
            JOIN courses c ON c.id = l.course_id
            {clause}
            GROUP BY rc.decision, rc.decided_by
            ORDER BY rc.decision, rc.decided_by
            """,
            params,
        )
        return curs.fetchall()

    @postgre_connection(__config)
    def delete(self, report_id: int, curs: cursor = None) -> bool:
        curs.execute("DELETE FROM reports WHERE id = %s RETURNING id", (report_id,))
        return bool(curs.fetchone())
