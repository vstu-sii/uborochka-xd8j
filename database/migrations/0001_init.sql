-- 0001_init.sql
-- Первая миграция: создаёт схему как она описана в docs/architecture/erd.puml
-- и database/schema.sql. Дальше схема меняется только новыми файлами
-- 0002_*.sql, 0003_*.sql — этот файл не редактируется задним числом.

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id                BIGSERIAL PRIMARY KEY,
    telegram_user_id  BIGINT NOT NULL UNIQUE,
    username          TEXT,
    full_name         TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assessments (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    telegram_photo_file_id  TEXT NOT NULL,
    score                   SMALLINT CHECK (score BETWEEN 1 AND 10),
    status                  TEXT NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'scored', 'failed')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    scored_at               TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_assessments_user_id ON assessments (user_id);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments (status);

CREATE TABLE IF NOT EXISTS recommendations (
    id             BIGSERIAL PRIMARY KEY,
    assessment_id  BIGINT NOT NULL REFERENCES assessments (id) ON DELETE CASCADE,
    text           TEXT NOT NULL,
    position       SMALLINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_recommendations_assessment_id
    ON recommendations (assessment_id);

COMMIT;
