from psycopg2.extensions import cursor
from settings import EducationDatabaseConfig

from ..connection import postgre_connection


class TeacherRepository:
    __config = EducationDatabaseConfig()

    @postgre_connection(__config)
    def get_credentials(self, login: str, curs: cursor = None) -> tuple[int, str] | None:
        """(id, хеш пароля) по логину."""
        curs.execute("SELECT id, password FROM teachers WHERE login = %s", (login,))
        row = curs.fetchone()
        return (row[0], row[1]) if row else None

    @postgre_connection(__config)
    def set_password_hash(self, user_id: int, password_hash: str, curs: cursor = None) -> None:
        curs.execute("UPDATE teachers SET password = %s WHERE id = %s", (password_hash, user_id))

    @postgre_connection(__config)
    def is_login_already_used(self, login: str, curs: cursor = None) -> bool:
        query = """
            SELECT 1
            FROM teachers
            WHERE login = %s
            """
        curs.execute(query, (login,))
        check = curs.fetchone()
        return bool(check)

    @postgre_connection(__config)
    def create(
        self,
        *,
        login: str,
        password: str,
        first_name: str,
        last_name: str,
        curs: cursor = None,
    ) -> int:
        query = """
            INSERT INTO teachers (login, password, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """
        curs.execute(query, (login, password, first_name, last_name))
        return int(curs.fetchone()[0])

    @postgre_connection(__config)
    def delete(self, teacher_id: int, curs: cursor = None) -> bool:
        query = """
            DELETE FROM teachers
            WHERE id = %s
            RETURNING id
            """
        curs.execute(query, (teacher_id,))
        return bool(curs.fetchone())

    @postgre_connection(__config)
    def get_by_id(self, teacher_id: int, curs: cursor = None) -> tuple[int, str, str, str] | None:
        query = """
            SELECT id, login, first_name, last_name
            FROM teachers
            WHERE id = %s
            """
        curs.execute(query, (teacher_id,))
        row = curs.fetchone()
        return row if row else None

    @postgre_connection(__config)
    def get_first_and_last_names(self, teacher_id: int, curs: cursor = None) -> tuple[str, str]:
        query = """
            SELECT first_name, last_name
            FROM teachers
            WHERE id = %s
            """
        curs.execute(query, (teacher_id,))
        row = curs.fetchone()
        if row is None:
            raise LookupError("user not found")
        return row[0], row[1]
