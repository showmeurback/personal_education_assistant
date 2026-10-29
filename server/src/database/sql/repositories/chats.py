import json
from datetime import datetime

from psycopg2.extensions import cursor

from settings import EducationDatabaseConfig
from ..connection import postgre_connection


class ChatRepository:
    __config = EducationDatabaseConfig()

    @postgre_connection(__config)
    def create_chat(self, student_id: int, course_id: int, name: str, curs: cursor = None) -> int:
        query = """
            INSERT INTO chats (student_id, course_id, name)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        curs.execute(query, (student_id, course_id, name))
        return int(curs.fetchone()[0])

    @postgre_connection(__config)
    def get_chat(self, chat_id: int, curs: cursor = None) -> tuple | None:
        query = """
            SELECT id, student_id, course_id, name, created_at::text
            FROM chats
            WHERE id = %s
        """
        curs.execute(query, (chat_id,))
        return curs.fetchone()

    @postgre_connection(__config)
    def get_student_chats(self, student_id: int, curs: cursor = None) -> list[tuple]:
        query = """
            SELECT ch.id, ch.name, ch.course_id, c.title, ch.created_at::text, ch.pinned_at IS NOT NULL
            FROM chats ch
            JOIN courses c ON c.id = ch.course_id
            WHERE ch.student_id = %s
            ORDER BY ch.pinned_at IS NULL, ch.pinned_at DESC, ch.created_at DESC
        """
        curs.execute(query, (student_id,))
        return curs.fetchall()

    @postgre_connection(__config)
    def add_message(self, chat_id: int, role: str, content: str, created_at: datetime | None = None,
                    meta: dict | None = None, curs: cursor = None) -> None:
        """created_at — момент отправки (UTC); для вопроса это время, когда студент его задал,
        а не время, когда ассистент закончил ответ."""
        query = """
            INSERT INTO chat_messages (chat_id, role, content, created_at, meta)
            VALUES (%s, %s, %s, COALESCE((%s::timestamptz AT TIME ZONE current_setting('TimeZone')), NOW()), %s::jsonb)
        """
        curs.execute(query, (chat_id, role, content, created_at, json.dumps(meta, ensure_ascii=False) if meta else None))

    @postgre_connection(__config)
    def set_pinned(self, chat_id: int, pinned: bool, curs: cursor = None) -> bool:
        query = "UPDATE chats SET pinned_at = CASE WHEN %s THEN NOW() END WHERE id = %s RETURNING id"
        curs.execute(query, (pinned, chat_id))
        return bool(curs.fetchone())

    @postgre_connection(__config)
    def delete_chat(self, chat_id: int, curs: cursor = None) -> bool:
        query = "DELETE FROM chats WHERE id = %s RETURNING id"
        curs.execute(query, (chat_id,))
        return bool(curs.fetchone())

    @postgre_connection(__config)
    def rename_chat(self, chat_id: int, name: str, curs: cursor = None) -> bool:
        query = "UPDATE chats SET name = %s WHERE id = %s RETURNING id"
        curs.execute(query, (name, chat_id))
        return bool(curs.fetchone())

    @postgre_connection(__config)
    def get_messages(self, chat_id: int, limit: int = 20, curs: cursor = None) -> list[tuple]:
        """Последние `limit` сообщений: (роль, текст, время отправки в UTC (ISO 8601), meta)."""
        query = """
            SELECT role, content, sent_at, meta FROM (
                SELECT id, role, content, meta, to_char((created_at AT TIME ZONE current_setting('TimeZone')) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS sent_at
                FROM chat_messages
                WHERE chat_id = %s
                ORDER BY id DESC
                LIMIT %s
            ) sub
            ORDER BY id ASC
        """
        curs.execute(query, (chat_id, limit))
        return curs.fetchall()
