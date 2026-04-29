# Test Payloads

Ready-to-use `curl` examples for every endpoint.  
Replace `USER_ID` and `TOKEN` with real values (see [Quick Setup](#quick-setup)).

---

## Quick Setup

```bash
# 1. Store your user ID
export USER_ID="347f7697-af76-48e5-be73-f966bab92ae5"

# 2. Get tokens
export TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\": \"$USER_ID\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

export REFRESH=$(curl -s -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\": \"$USER_ID\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['refresh_token'])")
```

---

## Auth

### POST /auth/token — Issue tokens

```bash
curl -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "347f7697-af76-48e5-be73-f966bab92ae5"
  }'
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### POST /auth/refresh — Get a new access token

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{
    "refresh_token": "<your_refresh_token>"
  }'
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Notifications

### POST /notifications — Send an email

```bash
curl -X POST http://localhost:8000/notifications \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"type\": \"transactional\",
    \"channel\": \"email\",
    \"subject\": \"Order Confirmed\",
    \"body\": \"Your order #1234 has been confirmed and will ship soon.\",
    \"extra_data\": {\"order_id\": \"1234\", \"amount\": 59.99}
  }"
```

---

### POST /notifications — Send an SMS

```bash
curl -X POST http://localhost:8000/notifications \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"type\": \"transactional\",
    \"channel\": \"sms\",
    \"body\": \"Your OTP is 482910. Expires in 10 minutes.\"
  }"
```

---

### POST /notifications — Send a push notification

```bash
curl -X POST http://localhost:8000/notifications \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"type\": \"promotional\",
    \"channel\": \"push\",
    \"subject\": \"Flash Sale\",
    \"body\": \"50% off everything for the next 2 hours!\",
    \"extra_data\": {\"promo_code\": \"FLASH50\", \"deep_link\": \"/sale\"}
  }"
```

---

### POST /notifications — Send an in-app notification

```bash
curl -X POST http://localhost:8000/notifications \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"type\": \"system_alert\",
    \"channel\": \"inapp\",
    \"subject\": \"Maintenance tonight\",
    \"body\": \"Scheduled maintenance on May 1st, 02:00–04:00 UTC.\"
  }"
```

---

### POST /notifications — Schedule a future notification

```bash
curl -X POST http://localhost:8000/notifications \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"type\": \"promotional\",
    \"channel\": \"email\",
    \"subject\": \"Your weekly digest\",
    \"body\": \"Here's what happened this week.\",
    \"scheduled_at\": \"2026-05-06T09:00:00Z\"
  }"
```

> `scheduled_at` — ISO 8601 datetime. Omit for immediate delivery.

---

**Field reference for `POST /notifications`:**

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `user_id` | UUID | ✅ | — |
| `type` | string | ✅ | `transactional`, `promotional`, `system_alert` |
| `channel` | string | ✅ | `email`, `sms`, `push`, `inapp` |
| `body` | string | ✅ | Non-empty string |
| `subject` | string | ❌ | Recommended for `email` / `push` |
| `extra_data` | object | ❌ | Any JSON object |
| `scheduled_at` | datetime | ❌ | ISO 8601 (e.g. `2026-05-01T09:00:00Z`) |

---

### GET /notifications/{id} — Get a notification

```bash
curl http://localhost:8000/notifications/1 \
  -H "Authorization: Bearer $TOKEN"
```

---

### PATCH /notifications/{id} — Mark as read

```bash
curl -X PATCH http://localhost:8000/notifications/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"is_read": true}'
```

### PATCH /notifications/{id} — Update status

```bash
curl -X PATCH http://localhost:8000/notifications/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status": "delivered"}'
```

> Valid `status` values: `pending`, `queued`, `delivered`, `failed`, `scheduled`

---

## Users

### GET /users/{user_id}/notifications — List all notifications for a user

```bash
curl "http://localhost:8000/users/$USER_ID/notifications" \
  -H "Authorization: Bearer $TOKEN"
```

---

### GET /users/{user_id}/preferences — Get preferences

```bash
curl "http://localhost:8000/users/$USER_ID/preferences" \
  -H "Authorization: Bearer $TOKEN"
```

---

### PUT /users/{user_id}/preferences — Update preferences

**Disable SMS:**
```bash
curl -X PUT "http://localhost:8000/users/$USER_ID/preferences" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"sms_enabled": false}'
```

**Set Do-Not-Disturb (10 PM – 8 AM):**
```bash
curl -X PUT "http://localhost:8000/users/$USER_ID/preferences" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"dnd_start_hour": 22, "dnd_end_hour": 8}'
```

**Limit promotional messages + disable push:**
```bash
curl -X PUT "http://localhost:8000/users/$USER_ID/preferences" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "push_enabled": false,
    "promotional": true,
    "max_promotional_per_day": 2
  }'
```

**Full reset to all-enabled:**
```bash
curl -X PUT "http://localhost:8000/users/$USER_ID/preferences" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "email_enabled": true,
    "sms_enabled": true,
    "push_enabled": true,
    "inapp_enabled": true,
    "transactional": true,
    "promotional": true,
    "system_alerts": true,
    "max_promotional_per_day": 5,
    "dnd_start_hour": null,
    "dnd_end_hour": null
  }'
```

> All preference fields are optional — only fields you include will be updated.

---

## Error Responses

| Status | When |
|--------|------|
| `401 Unauthorized` | Missing, expired, or invalid token |
| `404 Not Found` | User or notification ID does not exist |
| `422 Unprocessable Entity` | Channel or type is disabled by user preferences |
| `429 Too Many Requests` | Rate limit exceeded (100 req/min per IP) |
