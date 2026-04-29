# Scalable Notification Service

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-orange?logo=rabbitmq)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![Grafana](https://img.shields.io/badge/Grafana-Prometheus-F46800?logo=grafana)

A production-grade notification service built as a system design portfolio project. Handles multi-channel delivery (email, SMS, push, in-app WebSocket), user preferences, scheduled notifications, retry with exponential backoff, dead-letter queues, JWT auth, Redis rate limiting, and full observability via Prometheus + Grafana.

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
- **JWT authentication** — Bearer token required on all protected endpoints
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
| `inapp_service` | 8001 | FastAPI WebSocket server — real-time in-app delivery |
| `email_processor` | — | RabbitMQ consumer → SendGrid |
| `sms_processor` | — | RabbitMQ consumer → Twilio |
| `push_processor` | — | RabbitMQ consumer → FCM |
| `scheduler` | — | Polls DB every 60s, dispatches due scheduled notifications |
| `postgres` | 5432 | Primary data store |
| `redis` | 6379 | Preference cache + rate limiting |
| `rabbitmq` | 5672 / 15672 | Message broker (Management UI on 15672) |
| `prometheus` | 9090 | Metrics scraping |
| `grafana` | 3000 | Dashboards |

---

## API Endpoints

All endpoints require `Authorization: Bearer <token>`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/notifications` | Create and dispatch a notification |
| `GET` | `/notifications/:id` | Fetch notification by ID |
| `PATCH` | `/notifications/:id` | Update status or mark read/unread |
| `GET` | `/users/:id/notifications` | Paginated inbox (newest first) |
| `GET` | `/users/:id/preferences` | Fetch user notification preferences |
| `PUT` | `/users/:id/preferences` | Update preferences (partial update supported) |
| `GET` | `/health` | Health check (no auth required) |
| `GET` | `/metrics` | Prometheus metrics (no auth required) |

Interactive API docs: `http://localhost:8000/docs`

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
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

### Generate a JWT (for testing)

```python
from services.api.auth import create_access_token
token = create_access_token("my-service")
print(token)
```

---

## Project Structure

```
scalable-notification-service/
├── services/
│   ├── api/                      # FastAPI notification service
│   │   ├── auth.py               # JWT encode/decode + dependency
│   │   ├── config.py             # Pydantic settings
│   │   ├── logging_config.py     # structlog setup
│   │   ├── main.py               # App factory, lifespan, middleware
│   │   ├── cache/                # Redis async client
│   │   ├── db/                   # SQLAlchemy engine + session
│   │   ├── middleware/           # Rate limiting
│   │   ├── models/               # ORM models
│   │   ├── routers/              # notifications.py, users.py
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   └── services/             # Business logic (preference, notification, user)
│   ├── email_processor/          # RabbitMQ consumer → SendGrid
│   ├── sms_processor/            # RabbitMQ consumer → Twilio
│   ├── push_processor/           # RabbitMQ consumer → FCM
│   ├── inapp_service/            # WebSocket server (bypasses queue)
│   ├── scheduler/                # Polls DB, dispatches due notifications
│   └── shared/
│       └── base_consumer.py      # Shared retry + DLQ + DB logging logic
├── db/
│   └── init.sql                  # Full PostgreSQL schema + triggers
├── monitoring/
│   ├── prometheus.yml            # Scrape config
│   └── grafana/provisioning/     # Auto-provisioned datasource + dashboard
├── docs/
│   ├── architecture.md
│   └── architecture-diagram.svg
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

---

## What I Learned

This project was built to reinforce system design concepts:

- Decoupling ingestion from delivery with a message queue (RabbitMQ)
- Channel-specific consumers with independent scaling and failure modes
- Hot-path caching strategy (Redis) to protect the database at scale
- Promotional rate limiting using Redis atomic counters (no race conditions)
- Retry patterns (exponential backoff) and DLQ for at-least-once delivery guarantees
- Real-time vs. async delivery trade-offs (WebSocket vs. queue)
- Observability: Prometheus metrics, structured JSON logs, Grafana dashboards

---

## License

MIT — see [LICENSE](LICENSE)

