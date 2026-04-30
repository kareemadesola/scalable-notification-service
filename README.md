# Scalable Notification Service

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-orange?logo=rabbitmq)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![Grafana](https://img.shields.io/badge/Grafana-Prometheus-F46800?logo=grafana)

A production-grade notification service built as a system design portfolio project. Handles multi-channel delivery (email, SMS, push, in-app WebSocket), user preferences, scheduled notifications, retry with exponential backoff, dead-letter queues, JWT auth with refresh tokens, Redis rate limiting, and full observability via Prometheus + Grafana.

---

## Architecture

![Architecture Diagram](docs/architecture-diagram.svg)

> Full component descriptions: [docs/architecture.md](docs/architecture.md)

---

## Features

- **Multi-channel delivery** — email (SendGrid), SMS (Twilio), push (FCM), in-app (WebSocket)
- **User preferences** — per-channel opt-in/out, per-type opt-in/out (transactional / promotional / system alerts)
- **Promotional rate limiting** — configurable daily cap per user enforced via Redis counters
- **Do-not-disturb** — configurable quiet hours stored per user
- **Scheduled notifications** — set `scheduled_at` for future delivery; Scheduler Service polls and dispatches
- **Retry with exponential backoff** — 3 attempts (2s → 4s → 8s), then Dead Letter Queue
- **Dead Letter Queue (DLQ)** — failed messages preserved for manual review without data loss
- **Delivery logging** — every attempt recorded in `notification_logs` (status, attempt number, provider response)
- **Redis caching** — user preferences cached (5 min TTL) to eliminate hot-path DB reads
- **JWT authentication** — access token (60 min) + refresh token (7 days), Bearer scheme on all protected endpoints
- **API rate limiting** — 100 req/60s per IP via Redis sliding window; returns `429` with `Retry-After`
- **Prometheus + Grafana** — request rate, p95 latency, error rate, active connections; auto-provisioned dashboard
- **Structured JSON logging** — `structlog` throughout; JSON in production, colour console in development

---

## Scale Targets

| Metric | Target |
|--------|--------|
| Daily Active Users | 50 million |
| Notifications/day | 250 million |
| Peak throughput | ~17,000 notifications/sec |
| User data storage | ~50 GB |
| Daily notification storage | ~250 GB/day |
| Availability | 99.99% |

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI — ingestion, preference checks, publishes to RabbitMQ |
| `inapp_service` | 8001 | FastAPI WebSocket server — real-time in-app delivery (direct HTTP, no queue) |
| `email_processor` | — | RabbitMQ consumer → SendGrid |
| `sms_processor` | — | RabbitMQ consumer → Twilio |
| `push_processor` | — | RabbitMQ consumer → FCM |
| `scheduler` | — | Polls DB every 60s, dispatches due scheduled notifications |
| `postgres` | 5432 | Primary data store |
| `redis` | 6379 | Preference cache + rate limiting |
| `rabbitmq` | 5672 / 15672 | Message broker (Management UI on 15672) |
| `prometheus` | 9090 | Scrapes `/metrics` from the API |
| `grafana` | 3000 | Dashboards (auto-provisioned) |

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/token` | — | Issue access + refresh tokens by `user_id` |
| `POST` | `/auth/refresh` | — | Get a new access token using a refresh token |
| `POST` | `/notifications` | ✅ | Create and dispatch a notification |
| `GET` | `/notifications/:id` | ✅ | Fetch notification by ID |
| `PATCH` | `/notifications/:id` | ✅ | Update status or mark read/unread |
| `GET` | `/users/:id/notifications` | ✅ | Paginated inbox (newest first) |
| `GET` | `/users/:id/preferences` | ✅ | Fetch user notification preferences |
| `PUT` | `/users/:id/preferences` | ✅ | Update preferences (partial update supported) |
| `GET` | `/health` | — | Health check |
| `GET` | `/metrics` | — | Prometheus metrics |

Interactive API docs: `http://localhost:8000/docs`  
Ready-to-use curl examples: [docs/TEST_PAYLOADS.md](docs/TEST_PAYLOADS.md)

---

## Getting Started

### Prerequisites
- Docker & Docker Compose

### Run Locally

```bash
git clone https://github.com/kareemadesola/scalable-notification-service.git
cd scalable-notification-service

cp .env.example .env
# All channels default to mock mode — no real credentials needed

docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| In-App WebSocket | ws://localhost:8001/ws/{user_id} |
| RabbitMQ UI | http://localhost:15672 |
| Grafana | http://localhost:3000/d/notification-service |
| Prometheus | http://localhost:9090 |

### Authenticate

```bash
# 1. Get tokens
curl -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "<your-user-id>"}'

# 2. Use the access_token on protected endpoints
curl http://localhost:8000/users/<user-id>/notifications \
  -H "Authorization: Bearer <access_token>"

# 3. Refresh when expired (access token lasts 60 min, refresh token 7 days)
curl -X POST http://localhost:8000/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token": "<refresh_token>"}'
```

---

## Project Structure

```
scalable-notification-service/
├── services/
│   ├── api/                      # FastAPI notification service
│   │   ├── auth.py               # JWT encode/decode, access + refresh tokens
│   │   ├── config.py             # Pydantic settings (env-driven)
│   │   ├── logging_config.py     # structlog setup
│   │   ├── main.py               # App factory, lifespan, middleware
│   │   ├── cache/                # Redis async client
│   │   ├── db/                   # SQLAlchemy engine + session
│   │   ├── middleware/           # Rate limiting
│   │   ├── models/               # ORM models
│   │   ├── routers/              # auth.py, notifications.py, users.py
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   └── services/             # Business logic (preference, notification, user)
│   ├── email_processor/          # RabbitMQ consumer → SendGrid
│   ├── sms_processor/            # RabbitMQ consumer → Twilio
│   ├── push_processor/           # RabbitMQ consumer → FCM
│   ├── inapp_service/            # WebSocket server (direct HTTP, bypasses queue)
│   ├── scheduler/                # Polls DB, dispatches due notifications
│   └── shared/
│       └── base_consumer.py      # Shared retry + DLQ + DB logging logic
├── db/
│   └── init.sql                  # Full PostgreSQL schema + triggers
├── monitoring/
│   ├── prometheus.yml            # Scrape config (targets API /metrics)
│   └── grafana/provisioning/     # Auto-provisioned datasource + dashboard
├── docs/
│   ├── architecture.md           # Component descriptions
│   ├── architecture-diagram.svg  # Animated architecture diagram
│   ├── DATABASE.md               # Full schema reference + useful queries
│   ├── MONITORING.md             # Prometheus/Grafana guide + PromQL queries
│   ├── TEST_PAYLOADS.md          # Ready-to-use curl examples for every endpoint
│   ├── USER_GUIDE.md             # End-to-end usage guide
│   ├── USE_CASES.md              # Real-world use case scenarios
│   ├── TROUBLESHOOTING.md        # 14 bugs logged with root cause + fix
│   └── CHANGELOG.md              # Full commit history + future work
├── docker-compose.yml
└── .env.example
```

---

## Key Design Decisions

**Why RabbitMQ over Kafka?**
RabbitMQ is sufficient for this load and operationally simpler. Kafka would be the right swap at >10K sustained msg/sec where log replay and consumer group semantics matter.

**Why per-channel queues?**
Email, SMS, and push have different throughput, latency, and failure profiles. Separate queues allow each processor to scale independently without one channel blocking another.

**Why in-app bypasses the queue?**
In-app notifications require sub-second latency. The API writes to DB and broadcasts directly via the WebSocket service. If the user is offline, the notification sits in the DB and is served on the next `GET /users/:id/notifications` call.

**Why Redis for preferences?**
Preferences are read on every single notification dispatch. At 17K req/sec, a DB hit on every request would saturate PostgreSQL. Redis caches them for 5 minutes; cache is invalidated on every `PUT /users/:id/preferences`.

**Why exponential backoff + DLQ?**
Transient failures (network blips, provider downtime) should be retried. Permanent failures (invalid addresses, expired tokens) should not block the queue. DLQ preserves failed messages for manual inspection without data loss.

**Why access + refresh tokens?**
Short-lived access tokens (60 min) limit the exposure window if a token is leaked. Long-lived refresh tokens (7 days, configurable via `JWT_REFRESH_EXPIRE_DAYS`) avoid forcing users to re-authenticate frequently.

---

## What I Learned

- Decoupling ingestion from delivery with a message queue (RabbitMQ)
- Channel-specific consumers with independent scaling and failure modes
- Hot-path caching strategy (Redis) to protect the database at scale
- Promotional rate limiting using Redis atomic counters (no race conditions)
- Retry patterns (exponential backoff) and DLQ for at-least-once delivery guarantees
- Real-time vs. async delivery trade-offs (WebSocket vs. queue)
- JWT token lifecycle: access + refresh token patterns
- Observability: Prometheus metrics, structured JSON logs, Grafana dashboards

---

## Documentation

| Doc | Description |
|-----|-------------|
| [DATABASE.md](docs/DATABASE.md) | Schema reference, indexes, enums, useful queries |
| [TEST_PAYLOADS.md](docs/TEST_PAYLOADS.md) | Copy-paste curl examples for every endpoint |
| [MONITORING.md](docs/MONITORING.md) | Prometheus/Grafana guide with PromQL queries |
| [USER_GUIDE.md](docs/USER_GUIDE.md) | Full end-to-end usage walkthrough |
| [USE_CASES.md](docs/USE_CASES.md) | Real-world scenarios (e-commerce, fintech, SaaS…) |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | 14 bugs: root cause + fix |
| [CHANGELOG.md](docs/CHANGELOG.md) | Full commit history + future work |

---

## License

MIT — see [LICENSE](LICENSE)
