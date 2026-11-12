BEGIN;

ALTER TABLE users
    ALTER COLUMN telegram_user_id DROP NOT NULL;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS external_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_external_id
    ON users (external_id);

ALTER TABLE assessments
    ALTER COLUMN telegram_photo_file_id DROP NOT NULL;

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS room_id TEXT,
    ADD COLUMN IF NOT EXISTS maid_id TEXT,
    ADD COLUMN IF NOT EXISTS image_name TEXT,
    ADD COLUMN IF NOT EXISTS confidence TEXT,
    ADD COLUMN IF NOT EXISTS model_used TEXT,
    ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT false;

COMMIT;
