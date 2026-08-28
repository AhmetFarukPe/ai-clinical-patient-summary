"""Non-destructive SQLite schema setup for the patient-summary service."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_FILE = Path(__file__).with_name("hastane_yerel.db")


def _connect(db_file: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_file)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def _has_column(connection: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in connection.execute(f"PRAGMA table_info({table})"))


def initialize_database(db_file: str | Path = DEFAULT_DB_FILE) -> Path:
    """Create or upgrade tables without deleting existing patient records."""
    database_path = Path(db_file).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS hastalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tc_kimlik TEXT UNIQUE NOT NULL,
                ad TEXT NOT NULL,
                soyad TEXT NOT NULL,
                age INTEGER NOT NULL CHECK(age BETWEEN 0 AND 130),
                gender INTEGER NOT NULL CHECK(gender IN (0, 1, 2)),
                kayit_tarihi DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS olcumler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hasta_id INTEGER NOT NULL,
                hasta_token TEXT NOT NULL UNIQUE,
                facial_asymmetry_percentage INTEGER NOT NULL,
                oral_droop_percentage INTEGER NOT NULL,
                left_eye_openness_px REAL NOT NULL,
                right_eye_openness_px REAL NOT NULL,
                heart_rate_bpm INTEGER NOT NULL,
                respiratory_rate_bpm INTEGER NOT NULL,
                oxygen_saturation_percentage INTEGER NOT NULL,
                systolic_blood_pressure_mmhg INTEGER NOT NULL,
                diastolic_blood_pressure_mmhg INTEGER NOT NULL,
                measurement_confidence_score INTEGER NOT NULL DEFAULT 0,
                klinik_on_tani_ozeti TEXT NOT NULL DEFAULT '',
                ai_guven_skoru INTEGER NOT NULL DEFAULT 0,
                olcum_tarihi DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hasta_id) REFERENCES hastalar(id) ON DELETE CASCADE
            )
            """
        )

        for column, column_type in {
            "klinik_on_tani_ozeti": "TEXT NOT NULL DEFAULT ''",
            "ai_guven_skoru": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if not _has_column(connection, "olcumler", column):
                connection.execute(f"ALTER TABLE olcumler ADD COLUMN {column} {column_type}")

        connection.execute("CREATE INDEX IF NOT EXISTS idx_olcumler_tarih ON olcumler(olcum_tarihi DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_olcumler_token ON olcumler(hasta_token)")

    return database_path


if __name__ == "__main__":
    print(f"Veritabanı hazır: {initialize_database()}")
