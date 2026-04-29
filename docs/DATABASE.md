# Database Reference

PostgreSQL 16 — database: `notifications`  
Container: `ns_postgres` | User: `postgres`

---

## Quick Access

```bash
# Interactive shell
docker exec -it ns_postgres psql -U postgres -d notifications

# One-off query
docker exec ns_postgres psql -U postgres -d notifications -c "SELECT * FROM users;"
```

---

## Tables

### `users`

Stores registered users who can receive notifications.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | Primary key |
| `email` | `varchar(255)` | NOT NULL | — | Unique email address |
| `phone` | `varchar(50)` | NULL | — | Phone number for SMS |
| `device_token` | `varchar(512)` | NULL | — | Push notification token |
| `first_name` | `varchar(100)` | NOT NULL | — | First name |
| `last_name` | `varchar(100)` | NOT NULL | — | Last name |
| `created_at` | `timestamptz` | NOT NULL | `now()` | Record creation time |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | Last updated (auto-managed) |

**Indexes:** `users_pkey` (PK), `users_email_key` (unique), `idx_users_email`

---

### `notifications`

Every notification request sent through the system.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `bigint` | NOT NULL | auto-increment | Primary key |
| `user_id` | `uuid` | NOT NULL | — | FK → `users.id` (CASCADE delete) |
| `type` | `notification_type` | NOT NULL | — | `transactional`, `promotional`, `system_alert` |
| `channel` | `notification_channel` | NOT NULL | — | `email`, `sms`, `push`, `inapp` |
| `status` | `notification_status` | NOT NULL | `pending` | Current lifecycle status |
| `subject` | `varchar(255)` | NULL | — | Subject line (used by email) |
| `body` | `text` | NOT NULL | — | Notification body/message |
| `metadata` | `jsonb` | NULL | — | Arbitrary extra data from caller |
| `is_read` | `boolean` | NOT NULL | `false` | Whether user has read it (inapp) |
| `scheduled_at` | `timestamptz` | NULL | — | When to deliver; NULL = immediate |
| `created_at` | `timestamptz` | NOT NULL | `now()` | Record creation time |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | Last updated (auto-managed) |

**Indexes:**
- `notifications_pkey` (PK)
- `idx_notifications_user_id`
- `idx_notifications_status`
- `idx_notifications_scheduled` — partial index: only rows where `scheduled_at IS NOT NULL AND status = 'scheduled'`

---

### `user_preferences`

Per-user delivery preferences and quiet-hour settings. One row per user.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | Primary key |
| `user_id` | `uuid` | NOT NULL | — | FK → `users.id` (CASCADE delete) |
| `email_enabled` | `boolean` | NOT NULL | `true` | Allow email delivery |
| `sms_enabled` | `boolean` | NOT NULL | `true` | Allow SMS delivery |
| `push_enabled` | `boolean` | NOT NULL | `true` | Allow push delivery |
| `inapp_enabled` | `boolean` | NOT NULL | `true` | Allow in-app delivery |
| `transactional` | `boolean` | NOT NULL | `true` | Allow transactional type |
| `promotional` | `boolean` | NOT NULL | `true` | Allow promotional type |
| `system_alerts` | `boolean` | NOT NULL | `true` | Allow system alert type |
| `max_promotional_per_day` | `integer` | NOT NULL | `5` | Rate limit for promotional messages |
| `dnd_start_hour` | `smallint` | NULL | — | Do-not-disturb start (0–23) |
| `dnd_end_hour` | `smallint` | NULL | — | Do-not-disturb end (0–23) |
| `created_at` | `timestamptz` | NOT NULL | `now()` | Record creation time |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | Last updated (auto-managed) |

**Constraints:** `uq_user_preferences` (unique on `user_id`), DND hour range checks (0–23)

---

### `notification_logs`

Delivery attempt log for each notification. Multiple rows per notification for retries.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | `bigint` | NOT NULL | auto-increment | Primary key |
| `notification_id` | `bigint` | NOT NULL | — | FK → `notifications.id` (CASCADE delete) |
| `channel` | `notification_channel` | NOT NULL | — | Channel used for this attempt |
| `status` | `delivery_status` | NOT NULL | — | `success`, `failed`, `retrying` |
| `attempt_number` | `smallint` | NOT NULL | `1` | Which attempt this is |
| `provider_response` | `text` | NULL | — | Raw response from provider (error message, etc.) |
| `created_at` | `timestamptz` | NOT NULL | `now()` | When this attempt occurred |

**Indexes:** `notification_logs_pkey` (PK), `idx_logs_notification_id`, `idx_logs_status`

---

## Enum Types

| Type | Values |
|------|--------|
| `notification_type` | `transactional`, `promotional`, `system_alert` |
| `notification_channel` | `email`, `sms`, `push`, `inapp` |
| `notification_status` | `pending`, `queued`, `delivered`, `failed`, `scheduled` |
| `delivery_status` | `success`, `failed`, `retrying` |

---

## Relationships

```
users (1) ──────────────── (N) notifications
users (1) ──────────────── (1) user_preferences
notifications (1) ────── (N) notification_logs
```

All foreign keys use `ON DELETE CASCADE` — deleting a user removes all their notifications, preferences, and logs.

---

## Useful Queries

```sql
-- Notification counts by status and channel
SELECT status, channel, COUNT(*)
FROM notifications
GROUP BY status, channel
ORDER BY status, channel;

-- Recent notifications (last 20)
SELECT id, channel, status, subject, created_at
FROM notifications
ORDER BY created_at DESC
LIMIT 20;

-- Delivery success rate
SELECT
  channel,
  COUNT(*) FILTER (WHERE status = 'success') AS success,
  COUNT(*) FILTER (WHERE status = 'failed')  AS failed,
  COUNT(*) FILTER (WHERE status = 'retrying') AS retrying
FROM notification_logs
GROUP BY channel;

-- All users with their preference summary
SELECT
  u.email,
  p.email_enabled, p.sms_enabled, p.push_enabled, p.inapp_enabled,
  p.dnd_start_hour, p.dnd_end_hour
FROM users u
LEFT JOIN user_preferences p ON p.user_id = u.id;

-- Scheduled notifications pending delivery
SELECT id, user_id, channel, subject, scheduled_at
FROM notifications
WHERE status = 'scheduled'
ORDER BY scheduled_at;

-- Retry history for a specific notification
SELECT attempt_number, status, provider_response, created_at
FROM notification_logs
WHERE notification_id = <id>
ORDER BY attempt_number;

-- Failed notifications in the last 24 hours
SELECT n.id, u.email, n.channel, n.subject, n.updated_at
FROM notifications n
JOIN users u ON u.id = n.user_id
WHERE n.status = 'failed'
  AND n.updated_at >= now() - interval '24 hours'
ORDER BY n.updated_at DESC;
```

---

## Triggers

All tables have a `set_updated_at()` trigger that automatically updates `updated_at` on every `UPDATE`. You never need to set this column manually.
