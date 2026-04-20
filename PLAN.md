# Implementation Plan

## Tech Stack

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
│   ├── inapp_processor/            # RabbitMQ consumer → WebSocket broadcast
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
- [ ] In-App Processor (consumer + WebSocket broadcast)
- [ ] Dead Letter Queue (DLQ) handling
- [ ] Exponential backoff retry logic

## Phase 4 — Advanced Features
- [ ] User Preference Service (opt-in/out, per-channel rate limiting via Redis)
- [ ] Scheduler Service (store future notifications, cron poll + enqueue)
- [ ] Redis caching for user preferences

## Phase 5 — Observability & Polish
- [ ] Prometheus metrics (throughput, latency, failure rate per channel)
- [ ] Grafana dashboard
- [ ] Structured JSON logging (structlog) in every service
- [ ] JWT auth middleware
- [ ] API rate limiting middleware
- [ ] Delivery logs written to `notification_logs` table
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
