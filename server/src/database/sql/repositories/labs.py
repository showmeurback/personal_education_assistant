from psycopg2.extensions import cursor

from models.lab import NewLab

from settings import EducationDatabaseConfig
from ..connection import postgre_connection


class LabRepository:
    __config = EducationDatabaseConfig()

    @postgre_connection(__config)
    def get_labs(self, course_id: int, curs: cursor = None) -> list[tuple]:
        query = """
            SELECT id, number, title, task, min_words, required_sections
            FROM labs
            WHERE course_id = %s
            ORDER BY number, id
            """
        curs.execute(query, (course_id,))
        labs = curs.fetchall()
        return labs

    @postgre_connection(__config)
    def get_by_id(self, lab_id: int, curs: cursor = None) -> tuple | None:
        query = """
            SELECT id, number, title, task, course_id, min_words, required_sections
            FROM labs
            WHERE id = %s
            """
        curs.execute(query, (lab_id,))
        row = curs.fetchone()
        return row if row else None

    @postgre_connection(__config)
    def get_lab_task(self, lab_id: int, curs: cursor = None) -> str | None:
        query = """
            SELECT task
            FROM labs
            WHERE id = %s
            """
        curs.execute(query, (lab_id,))
        row = curs.fetchone()
        return row[0] if row else None

    @postgre_connection(__config)
    def create(self, lab: NewLab, course_id: int, curs: cursor = None) -> int:
        query = """
            INSERT INTO labs
            (number, title, task, course_id, min_words, required_sections)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """
        curs.execute(query, (lab.number, lab.title, lab.task, course_id,
                             lab.min_words, lab.required_sections))
        return curs.fetchone()[0]

    @postgre_connection(__config)
    def update(self, lab_id: int, *, number: int, title: str, task: str | None,
               min_words: int | None = None, required_sections: str | None = None,
               curs: cursor = None) -> bool:
        query = """
            UPDATE labs
            SET number = %s, title = %s, task = %s, min_words = %s, required_sections = %s
            WHERE id = %s
            RETURNING id
            """
        curs.execute(query, (number, title, task, min_words, required_sections, lab_id))
        return bool(curs.fetchone())

    @postgre_connection(__config)
    def delete(self, lab_id: int, curs: cursor = None) -> bool:
        query = """
            DELETE FROM labs
            WHERE id = %s
            RETURNING id
            """
        curs.execute(query, (lab_id,))
        return bool(curs.fetchone())
