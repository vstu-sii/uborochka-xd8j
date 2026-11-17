import os
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "database" / "migrations"


def apply_migrations() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before applying migrations")

    with psycopg.connect(
        database_url, connect_timeout=10, autocommit=True
    ) as connection:
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            connection.execute(migration.read_text(encoding="utf-8"))


if __name__ == "__main__":
    apply_migrations()
