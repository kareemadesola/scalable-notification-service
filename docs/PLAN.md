# Implementation Plan

## Status: ✅ Complete — All phases implemented, tested end-to-end, and deployed

---

## Tech Stack

| Layer        | Choice                                      |
|--------------|---------------------------------------------|
| API          | FastAPI (async)                             |
| Queue        | RabbitMQ via aio-pika                       |
| Database     | PostgreSQL via asyncpg + SQLAlchemy (async) |
| Cache        | Redis via redis-py (async)                  |
| WebSockets   | FastAPI built-in WebSocket support          |
| Email        | SendGrid SDK (mock mode by default)         |
| SMS          | Twilio Python SDK (mock mode by default)    |
| Push         | FCM (mock mode by default)                  |
| Monitoring   | Prometheus + Grafana                        |
| Containers   | Docker Compose (11 services)                |
| Auth         | JWT via python-jose                         |
| Logging      | structlog (JSON in prod, coloured in dev)   |

---

## Actual Project Structure

```
scalable-notification-service/
├── docker-compose.yml
├── .env / .env.example
├── services/
│   ├── api/                        # FastAPI notification service
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── config.py               # Pydantic settings
│   │   ├── auth.py                 # JWT create/verify
│   │   ├── logging_config.py       # structlog setup
│   │   ├── routers/
│   │   │   ├── notifications.py
│   │   │   └── users.py
│   │   ├── models/models.py
│   │   ├── schemas/
│   │   │   ├── notification.py
│   │   │   └── user.py
│   │   ├── services/
│   │   │   ├── notification_service.py
│   │   │   ├── preference_service.py
│   │   │   └── user_service.py
│   │   ├── db/database.py
│   │   ├── mq/publisher.py         # (originally queue/ — renamed to avoid stdlib conflict)
│   │   ├── cache/redis_client.py
│   │   └── middleware/rate_limit.py
│   ├── shared/base_consumer.py     # Abstract base — retry, DLQ, logging
│   ├── email_processor/            # RabbitMQ consumer → SendGrid
│   ├── sms_processor/              # RabbitMQ consumer → Twilio
│   ├── push_processor/             # RabbitMQ consumer → FCM
│   ├── inapp_service/              # WebSocket server, direct DB + broadcast
│   └── scheduler/                  # Polls DB every 60s, dispatches due notifications
├── db/init.sql                     # Full schema with enums, triggers, indexes
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/provisioning/       # Auto-provisioned datasource + dashboard
└── docs/
    ├── architecture.md
    ├── architecture-diagram.svg
    ├── notification-flow.svg       # Animated dispatch flow
    ├── preference-flow.svg         # Animated preference gate flowchart
    ├── PLAN.md
    ├── TROUBLESHOOTING.md
    ├── USE_CASES.md
    └── USER_GUIDE.md               # Full user guide with E2E test suite
```

---

## Phase 1 — Core Infrastructure ✅
- [x] Docker Compose (PostgreSQL, RabbitMQ, Redis, Prometheus, Grafana)
- [x] Database schema (`init.sql`) — enums, triggers, partial indexes
- [x] FastAPI app skeleton with health check
- [x] SQLAlchemy async models
- [x] RabbitMQ publisher utility

## Phase 2 — API Endpoints ✅
- [x] `POST /notifications` — validate, check user prefs, publish to queue
- [x] `GET /notifications/:id` — fetch notification by ID
- [x] `GET /users/:id/notifications` — user inbox (paginated)
- [x] `PATCH /notifications/:id` — mark read/unread, update status
- [x] `GET /users/:id/preferences` — fetch user settings
- [x] `PUT /users/:id/preferences` — update user settings

## Phase 3 — Channel Processors ✅
- [x] Email Processor (consumer + SendGrid mock)
- [x] SMS Processor (consumer + Twilio mock)
- [x] Push Processor (consumer + FCM mock)
- [x] In-App Service (WebSocket server, direct write to DB + broadcast)
- [x] Dead Letter Queue (DLQ) — `email.dlq`, `sms.dlq`, `push.dlq`
- [x] Exponential backoff retry logic (3 attempts, 2s/4s/8s)

## Phase 4 — Advanced Features ✅
- [x] User Preference Service (opt-in/out per channel and type)
- [x] Per-channel rate limiting via Redis atomic counters
- [x] Redis caching for user preferences (5 min TTL, cache invalidation on update)
- [x] Scheduler Service (polls DB every 60s, dispatches `scheduled_at <= NOW()`)

## Phase 5 — Observability & Polish ✅
- [x] Prometheus metrics (throughput, latency, error rate per endpoint)
- [x] Grafana dashboard (auto-provisioned)
- [x] Structured JSON logging (structlog) in every service
- [x] JWT auth middleware on all endpoints
- [x] API rate limiting middleware (100 req/60s per IP, Redis sliding window)
- [x] Delivery logs written to `notification_logs` table
- [x] Architecture diagram (animated SVG)
- [x] README polished
- [x] USER_GUIDE.md with full E2E test suite
- [x] USE_CASES.md with 6 real-world scenarios
- [x] TROUBLESHOOTING.md (14 issues logged)

---

## Bugs Fixed During Testing

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for full details on all 14 issues. Key ones:

| # | Bug | Fix |
|---|-----|-----|
| 1 | Docker `COPY ../shared` crossed build context | Changed build context to `./services/` |
| 6 | `queue/` folder shadowed Python built-in | Renamed to `mq/` |
| 7 | `Notification.metadata` reserved by SQLAlchemy | Renamed to `extra_data` |
| 8 | `PrintLogger` has no `.name` attribute | Switched to `stdlib.LoggerFactory()` |
| 13 | FK violation — processor consumed message before DB commit | Moved `db.commit()` before `publisher.publish()` |

---

## Scale Targets (for README / interviews)
- **Users:** 50 million daily active
- **Notifications/day:** 250 million (50M users × 5 avg)
- **Peak throughput:** ~17,000 notifications/second (1M in 60 seconds)
- **Storage (user data):** ~50 GB
- **Storage (daily notifications):** ~250 GB/day

## Key Design Decisions (for interviews)
1. **RabbitMQ** decouples ingestion from delivery — absorbs traffic spikes
2. **Per-channel queues** allow independent scaling of each processor
3. **Redis** caches user preferences to avoid hot-path DB reads
4. **Commit before publish** — DB transaction committed before RabbitMQ publish to prevent FK violations in processors
5. **`start_period` on health checks** — gives slow-starting services (RabbitMQ ~90s) grace time before retry counter starts
6. **Exponential backoff + DLQ** — failed messages retry 3 times then land in dead-letter queue for inspection, not silent loss

| Layer        | Choice                                      |
|--------------|---------------------------------------------|
| API          | FastAPI (async)                             |
| Queue        | RabbitMQ via aio-pika                       |
| Database     | PostgreSQL via asyncpg + SQLAlchemy (async) |
| Cache        | Redis via redis-py (async)                  |
| WebSockets   | FastAPI built-in WebSocket support          |
| Email        | SendGrid SDK (sandbox/mock)                 |
| SMS          | Twilio Python SDK (sandbox/mock)            |
| Push         | FCM mock                                    |
| Monitoring   | Prometheus + Grafana                        |
| Containers   | Docker Compose                              |

---

## Project Structure (Target)

```
scalable-notification-service/
├── docker-compose.yml
├── .env.example
├── services/
│   ├── api/                        # FastAPI notification service
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── notifications.py
│   │   │   └── users.py
│   │   ├── models/
│   │   │   ├── notification.py
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── notification.py
│   │   │   └── user.py
│   │   ├── db/
│   │   │   ├── database.py
│   │   │   └── migrations/
│   │   ├── queue/
│   │   │   └── publisher.py
│   │   ├── cache/
│   │   │   └── redis_client.py
│   │   └── requirements.txt
│   ├── email_processor/            # RabbitMQ consumer → SendGrid
│   │   ├── Dockerfile
│   │   ├── consumer.py
│   │   └── requirements.txt
│   ├── sms_processor/              # RabbitMQ consumer → Twilio
│   │   ├── Dockerfile
│   │   ├── consumer.py
│   │   └── requirements.txt
│   ├── push_processor/             # RabbitMQ consumer → FCM mock
│   │   ├── Dockerfile
│   │   ├── consumer.py
│   │   └── requirements.txt
│   ├── inapp_service/              # WebSocket server (bypasses queue, direct delivery)
│   │   ├── Dockerfile
│   │   ├── consumer.py
│   │   └── requirements.txt
│   └── scheduler/                  # Cron job polls DB, enqueues future notifications
│       ├── Dockerfile
│       ├── scheduler.py
│       └── requirements.txt
├── db/
│   └── init.sql                    # Initial schema
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       └── dashboards/
│           └── notification.json
└── docs/
    └── architecture.md
```

---

## Phase 1 — Core Infrastructure
- [ ] Docker Compose (PostgreSQL, RabbitMQ, Redis, Prometheus, Grafana)
- [ ] Database schema (`init.sql`)
- [ ] FastAPI app skeleton with health check
- [ ] SQLAlchemy async models
- [ ] RabbitMQ publisher utility

## Phase 2 — API Endpoints
- [ ] `POST /notifications` — validate, check user prefs, publish to queue
- [ ] `GET /notifications/:id` — fetch notification by ID
- [ ] `GET /users/:id/notifications` — user inbox (paginated)
- [ ] `PATCH /notifications/:id` — mark read/unread
- [ ] `GET /users/:id/preferences` — fetch user settings
- [ ] `PUT /users/:id/preferences` — update user settings

## Phase 3 — Channel Processors
- [ ] Email Processor (consumer + SendGrid mock)
- [ ] SMS Processor (consumer + Twilio mock)
- [ ] Push Processor (consumer + FCM mock)
- [ ] In-App Service (WebSocket server, direct write to DB, bypasses queue)
- [ ] Dead Letter Queue (DLQ) handling
- [ ] Exponential backoff retry logic

## Phase 4 — Advanced Features
- [ ] User Preference Service (opt-in/out, per-channel rate limiting via Redis)
- [ ] Scheduler Service (store future notifications, cron poll + enqueue)
- [ ] Redis caching for user preferences

## Phase 5 — Observability & Polish
- [x] Prometheus metrics (throughput, latency, failure rate per channel)
- [x] Grafana dashboard
- [x] Structured JSON logging (structlog) in every service
- [x] JWT auth middleware
- [x] API rate limiting middleware
- [x] Delivery logs written to `notification_logs` table
- [ ] Architecture diagram (Excalidraw / draw.io)
- [ ] Final README polish

---

## Scale Targets (for README / interviews)
- **Users:** 50 million daily active
- **Notifications/day:** 250 million (50M users × 5 avg)
- **Peak throughput:** ~17,000 notifications/second (1M in 60 seconds)
- **Storage (user data):** ~50 GB
- **Storage (daily notifications):** ~250 GB/day

## Key Design Decisions (for interviews)
1. **RabbitMQ** decouples ingestion from delivery — absorbs traffic spikes
2. **Per-channel queues** allow independent scaling of each processor
3. **Redis** caches user preferences to avoid hot-path DB reads
4. **DLQ** captures failed deliveries for manual review without data loss
5. **Scheduler** uses time-partitioned table for efficient future-notification polling
6. **WebSockets** for in-app (low latency); async queue for other channels
7. Would swap RabbitMQ → **Kafka** at >10K sustained msg/sec for log compaction and replay
