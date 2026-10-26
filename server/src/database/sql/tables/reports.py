from psycopg2.extensions import cursor

from models.enums import ReportStatus
from settings import EducationDatabaseConfig
from ..connection import postgre_connection

_config = EducationDatabaseConfig()


@postgre_connection(_config)
def _create_report_status_enum(*, curs: cursor = None) -> None:
    query = """
        DO $$
        BEGIN
            CREATE TYPE report_status AS ENUM (%s, %s, %s);
        EXCEPTION
            WHEN duplicate_object THEN
                NULL;
        END $$;
        """
    curs.execute(query, (
        ReportStatus.PENDING.value,
        ReportStatus.APPROVED.value,
        ReportStatus.NOT_APPROVED.value
    ))


@postgre_connection(_config)
def _create_table_reports(curs: cursor = None) -> None:
    query = """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            lab_id INT NOT NULL,
            student_id INT NOT NULL,
            status report_status DEFAULT 'pending',
            url TEXT,
            comment TEXT,
            CONSTRAINT fk_reports_lab
                FOREIGN KEY (lab_id)
                REFERENCES labs (id)
                ON DELETE CASCADE,
            CONSTRAINT fk_reports_student
                FOREIGN KEY (student_id)
                REFERENCES students (id)
                ON DELETE CASCADE
        )
    """
    curs.execute(query)


@postgre_connection(_config)
def _extend_report_status_enum(curs: cursor = None) -> None:
    # Статусы гибридной проверки: отклонён автоматически / требует ручной проверки
    for value in (ReportStatus.AI_REJECTED.value, ReportStatus.MANUAL_REVIEW.value, ReportStatus.CHECKING.value):
        curs.execute(f"ALTER TYPE report_status ADD VALUE IF NOT EXISTS '{value}'")


@postgre_connection(_config)
def _alter_reports_add_columns(curs: cursor = None) -> None:
    for ddl in (
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'gdoc'",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS filename TEXT",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS file_path TEXT",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS text TEXT",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS ai_summary TEXT",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()",
    ):
        curs.execute(ddl)


@postgre_connection(_config)
def _create_table_report_checks(curs: cursor = None) -> None:
    """Протокол гибридной проверки: по одной записи на каждую отправку отчёта."""
    curs.execute("""
        CREATE TABLE IF NOT EXISTS report_checks (
            id SERIAL PRIMARY KEY,
            report_id INT NOT NULL REFERENCES reports (id) ON DELETE CASCADE,
            decision TEXT NOT NULL,
            decided_by TEXT NOT NULL,
            final_score REAL,
            max_similarity REAL,
            llm_calls INT NOT NULL DEFAULT 0,
            duration_ms INT NOT NULL DEFAULT 0,
            protocol JSONB NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)
    curs.execute("CREATE INDEX IF NOT EXISTS idx_report_checks_report ON report_checks (report_id)")


@postgre_connection(_config)
def _create_active_report_index(curs: cursor = None) -> None:
    """Не более одного «активного» отчёта студента по лабораторной работе.

    Проверка «нет ли активного отчёта» и вставка нового выполняются разными запросами,
    поэтому без ограничения два одновременных запроса (двойной клик) создавали два отчёта.
    Частичный уникальный индекс делает вставку второго отчёта невозможной на уровне БД.
    Ранее созданные дубликаты (если есть) переводятся в «ручную проверку» кроме последнего.
    """
    curs.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY student_id, lab_id ORDER BY created_at DESC, id DESC) AS rn
            FROM reports WHERE status IN ('checking', 'pending', 'manual-review', 'approved')
        )
        UPDATE reports SET status = 'not-approved',
               comment = COALESCE(comment, 'Повторная отправка: учитывается последняя версия отчёта')
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
    """)
    curs.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_active_per_lab ON reports (student_id, lab_id)
        WHERE status IN ('checking', 'pending', 'manual-review', 'approved')
    """)


def create_reports_tables():
    _create_report_status_enum()
    _extend_report_status_enum()
    _create_table_reports()
    _alter_reports_add_columns()
    _create_table_report_checks()
    _create_active_report_index()
