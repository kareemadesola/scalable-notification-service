# Changelog & Future Work

---

## Changelog

### April 29, 2026

| Commit | Description |
|--------|-------------|
| `3be10b2` | chore: remove accidentally committed subject file |
| `eab4af0` | fix: add `refresh_expires_in` to token response and `JWT_REFRESH_EXPIRE_DAYS` env var |
| `d96c7b5` | feat: add `POST /auth/token`, `POST /auth/refresh` endpoints and `docs/TEST_PAYLOADS.md` |
| `a6a92b3` | docs: add `DATABASE.md` with full schema reference and useful queries |
| `85df9d2` | docs: add `MONITORING.md` with Prometheus/Grafana guide |
| `b0a4cf9` | feat: add docs, fix response serialization bugs, end-to-end verified |
| `cb978fc` | fix: resolve all startup and runtime bugs (port conflicts, health checks, retry loops, DLQ, FK race condition) |
| `64eeb05` | fix: processor Dockerfiles — use `services/` as build context so `shared/` is accessible |
| `694b12a` | docs: final README polish — services table, full structure, expanded design decisions |
| `0cb144d` | feat: phase 5 — structlog JSON logging, JWT auth, Redis rate limiting, Grafana dashboard |
| `ef7e147` | feat: phase 4 — scheduler service (polls DB, dispatches due notifications) |
| `a4e5c8e` | feat: phase 3 — email/SMS/push processors, in-app WebSocket service, DLQ, exponential backoff |
| `12ea1eb` | feat: phase 2 — API endpoints, schemas, preference/notification/user service layer |

### April 27, 2026

| Commit | Description |
|--------|-------------|
| `3c6e42a` | feat: phase 1 — Docker Compose, DB schema, FastAPI skeleton, models, RabbitMQ publisher |
| `041cd02` | docs: fix inapp service naming — it bypasses queue, not a RabbitMQ consumer |
| `a393b17` | docs: remove redundant ASCII flow from README |
| `f42853a` | docs: remove redundant ASCII diagram, SVG is the source of truth |
| `445446b` | docs: add SVG architecture diagram to README and architecture.md |

### April 20, 2026

| Commit | Description |
|--------|-------------|
| `e9cade7` | docs: improve architecture diagram — remove inapp queue, fix Prometheus scrape arrows |
| `8ed8958` | chore: initial project structure, README, architecture docs, and plan |
| `a5bb79f` | chore: initial project structure, README, architecture docs, and plan |

---

## Future Work

### Auth
- **Token revocation** — store invalidated tokens in Redis so logout actually invalidates the token
- **Refresh token rotation** — issue a new refresh token on every `POST /auth/refresh` call
- **Login with email/password** — add password field to `users`, hash with bcrypt, issue tokens on credential login

### Notifications
- **Real email delivery** — connect SendGrid (`MOCK_EMAIL=false`, `SENDGRID_API_KEY`)
- **Real SMS delivery** — connect Twilio (`MOCK_SMS=false`, `TWILIO_ACCOUNT_SID`)
- **Real push delivery** — connect FCM (`MOCK_PUSH=false`, `FCM_SERVER_KEY`)
- **Webhook channel** — new channel type that POSTs to a user-configured URL
- **Notification templates** — store reusable templates, render with dynamic variables at send time
- **Bulk notifications** — single `POST /notifications/bulk` to notify multiple users at once

### Users
- **User registration endpoint** — `POST /users` with email + password
- **User deletion endpoint** — `DELETE /users/{id}`
- **Multiple device tokens** — support one user owning many devices for push notifications

### Reliability
- **Dead letter queue (DLQ) monitoring** — alert or dashboard when messages land in DLQ
- **Retry count cap** — stop retrying after N failures and mark `status=failed` with reason
- **Idempotency keys** — prevent duplicate notifications when clients retry on timeout

### Infrastructure
- **HTTPS/TLS** — add nginx reverse proxy with SSL termination
- **Kubernetes manifests** — Helm chart for deploying to a cloud cluster
- **CI/CD pipeline** — GitHub Actions: lint + test + build + push Docker image on merge to `main`
- **Integration tests** — automated test suite that spins up the full stack and runs all endpoints
