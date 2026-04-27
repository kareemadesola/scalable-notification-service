-- =============================================================
-- Notification Service — Initial Schema
-- =============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    phone       VARCHAR(50),
    device_token VARCHAR(512),           -- FCM push token
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users (email);

-- ── User Preferences ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- channel opt-ins
    email_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    sms_enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    push_enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    inapp_enabled       BOOLEAN NOT NULL DEFAULT TRUE,

    -- notification type opt-ins
    transactional       BOOLEAN NOT NULL DEFAULT TRUE,
    promotional         BOOLEAN NOT NULL DEFAULT TRUE,
    system_alerts       BOOLEAN NOT NULL DEFAULT TRUE,

    -- rate limits (per day)
    max_promotional_per_day INTEGER NOT NULL DEFAULT 5,

    -- do-not-disturb window (UTC hour 0–23, NULL = disabled)
    dnd_start_hour      SMALLINT CHECK (dnd_start_hour BETWEEN 0 AND 23),
    dnd_end_hour        SMALLINT CHECK (dnd_end_hour BETWEEN 0 AND 23),

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_preferences UNIQUE (user_id)
);

-- ── Notifications ─────────────────────────────────────────────
CREATE TYPE notification_channel AS ENUM ('email', 'sms', 'push', 'inapp');
CREATE TYPE notification_type    AS ENUM ('transactional', 'promotional', 'system_alert');
CREATE TYPE notification_status  AS ENUM ('pending', 'queued', 'delivered', 'failed', 'scheduled');

CREATE TABLE IF NOT EXISTS notifications (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            notification_type    NOT NULL,
    channel         notification_channel NOT NULL,
    status          notification_status  NOT NULL DEFAULT 'pending',
    subject         VARCHAR(255),
    body            TEXT NOT NULL,
    metadata        JSONB,                  -- extra channel-specific data
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    scheduled_at    TIMESTAMPTZ,            -- NULL = send immediately
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_id   ON notifications (user_id);
CREATE INDEX idx_notifications_status    ON notifications (status);
CREATE INDEX idx_notifications_scheduled ON notifications (scheduled_at)
    WHERE scheduled_at IS NOT NULL AND status = 'scheduled';

-- ── Notification Logs ─────────────────────────────────────────
CREATE TYPE delivery_status AS ENUM ('success', 'failed', 'retrying');

CREATE TABLE IF NOT EXISTS notification_logs (
    id                  BIGSERIAL PRIMARY KEY,
    notification_id     BIGINT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    channel             notification_channel NOT NULL,
    status              delivery_status NOT NULL,
    attempt_number      SMALLINT NOT NULL DEFAULT 1,
    provider_response   TEXT,               -- raw response or error from SendGrid/Twilio/FCM
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_logs_notification_id ON notification_logs (notification_id);
CREATE INDEX idx_logs_status          ON notification_logs (status);

-- ── updated_at auto-update trigger ────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_notifications_updated_at
    BEFORE UPDATE ON notifications
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
