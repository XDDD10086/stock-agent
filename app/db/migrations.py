from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def apply_sqlite_compat_migrations(engine: Engine) -> None:
    with engine.begin() as conn:
        if conn.dialect.name != "sqlite":
            return

        has_schedule_table = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schedules' LIMIT 1")
        ).scalar_one_or_none()
        if has_schedule_table is None:
            return

        column_rows = conn.execute(text("PRAGMA table_info(schedules)")).fetchall()
        existing_columns = {row[1] for row in column_rows}

        additions = {
            "run_at_utc": "DATETIME",
            "time_of_day": "VARCHAR(5)",
            "days_of_week": "VARCHAR(64)",
        }
        for column_name, column_type in additions.items():
            if column_name in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE schedules ADD COLUMN {column_name} {column_type}"))
