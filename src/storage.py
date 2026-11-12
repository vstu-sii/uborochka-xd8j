"""Persistence for inspection results."""

import os

import psycopg

from src.vision.analyze import CleaningAssessment


class DatabaseNotConfigured(RuntimeError):
    """Raised when persistence is requested without a database URL."""


def check_database() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not set")

    with psycopg.connect(database_url, connect_timeout=2) as connection:
        connection.execute("SELECT 1")


def create_assessment(
    *,
    maid_id: str,
    room_id: str,
    image_name: str,
    assessment: CleaningAssessment,
) -> dict[str, int]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not set")

    with psycopg.connect(database_url) as connection:
        user_id = connection.execute(
            """
            INSERT INTO users (external_id, username)
            VALUES (%s, %s)
            ON CONFLICT (external_id)
            DO UPDATE SET username = EXCLUDED.username
            RETURNING id
            """,
            (maid_id, maid_id),
        ).fetchone()[0]

        assessment_id = connection.execute(
            """
            INSERT INTO assessments (
                user_id, room_id, maid_id, image_name, score, status,
                confidence, model_used, is_demo, scored_at
            )
            VALUES (%s, %s, %s, %s, %s, 'scored', %s, %s, %s, now())
            RETURNING id
            """,
            (
                user_id,
                room_id,
                maid_id,
                image_name,
                assessment.score,
                assessment.confidence,
                assessment.model_used,
                assessment.is_demo,
            ),
        ).fetchone()[0]

        connection.cursor().executemany(
            """
            INSERT INTO recommendations (assessment_id, text, position)
            VALUES (%s, %s, %s)
            """,
            [
                (assessment_id, text, position)
                for position, text in enumerate(assessment.recommendations)
            ],
        )

    return {"id": assessment_id}
