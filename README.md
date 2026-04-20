# Scalable Notification Service

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-orange?logo=rabbitmq)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![Grafana](https://img.shields.io/badge/Grafana-Prometheus-F46800?logo=grafana)

A production-grade notification service built as a system design portfolio project. Supports multi-channel delivery (email, SMS, push, in-app), user preferences, scheduled notifications, retry with dead-letter queues, and full observability via Prometheus + Grafana.

---

## Architecture

> Architecture diagram coming soon (see `docs/architecture.md`)

### High-Level Flow

```
Client / Internal Service
        │
        ▼
  API Gateway (FastAPI)
        │
        ├── Check User Preferences (Redis cache → PostgreSQL)
        ├── Schedule? → Scheduler Service
        │
        ▼
  RabbitMQ (per-channel topics)
  ┌──────┬──────┬──────┬────────┐
  Email  SMS   Push  In-App
    │      │     │       │
    ▼      ▼     ▼       ▼
 SendGrid Twilio FCM  WebSocket
        │
        ▼
  notification_logs (PostgreSQL)
        │
  Dead Letter Queue (on failure)
```

---

## Features

- **Multi-channel delivery** — email, SMS, push notifications, in-app (WebSocket)
- **User preferences** — per-channel opt-in/out, daily rate limiting
- **Scheduled notifications** — deliver at a future time via Scheduler Service
- **Retry with exponential backoff** — automatic retry on transient failures
- **Dead Letter Queue (DLQ)** — failed messages captured for manual review
- **Delivery logging** — full audit trail in `notification_logs` table
- **Redis caching** — user preferences cached to reduce DB load
- **Prometheus + Grafana** — metrics: throughput, latency, failure rate per channel; structured JSON logs via `structlog`
- **JWT authentication** — secured API endpoints
- **Rate limiting** — per-client API throttling

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

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/notifications` | Create and dispatch a notification |
| `GET` | `/notifications/:id` | Fetch notification by ID |
| `GET` | `/users/:id/notifications` | Paginated user inbox |
| `PATCH` | `/notifications/:id` | Mark read/unread |
| `GET` | `/users/:id/preferences` | Fetch user notification preferences |
| `PUT` | `/users/:id/preferences` | Update user preferences |

Full interactive API docs available at `http://localhost:8000/docs` (Swagger UI) when running locally.

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.12+

### Run Locally

```bash
git clone https://github.com/YOUR_USERNAME/scalable-notification-service.git
cd scalable-notification-service

cp .env.example .env
# Fill in your credentials (SendGrid, Twilio, etc.) or leave mocks enabled

docker compose up --build
```

Services will be available at:
| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| RabbitMQ UI | http://localhost:15672 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

---

## Project Structure

```
scalable-notification-service/
├── services/
│   ├── api/                  # FastAPI notification service
│   ├── email_processor/      # RabbitMQ consumer → SendGrid
│   ├── sms_processor/        # RabbitMQ consumer → Twilio
│   ├── push_processor/       # RabbitMQ consumer → FCM
│   ├── inapp_processor/      # RabbitMQ consumer → WebSocket
│   └── scheduler/            # Polls DB, enqueues future notifications
├── db/
│   └── init.sql              # Database schema
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/dashboards/
├── docker-compose.yml
└── .env.example
```

---

## Key Design Decisions

**Why RabbitMQ over Kafka?**
RabbitMQ is sufficient for this scale and simpler to operate. At >10K sustained msg/sec with replay/audit requirements, Kafka would be the right choice.

**Why per-channel queues?**
Each channel (email, SMS, push, in-app) has different throughput, latency requirements, and failure modes. Separate queues allow independent scaling.

**Why Redis for preferences?**
User preferences are read on every notification dispatch. Caching them avoids a hot-path DB read that would become a bottleneck at scale.

**Why WebSockets for in-app only?**
Email/SMS/push have inherent async delivery via third-party providers. In-app benefits from real-time push; other channels don't require persistent connections.

---

## What I Learned

This project was built to reinforce system design concepts after studying notification service architecture:

- Decoupling ingestion from delivery using a message queue
- Channel-specific processing with independent scaling
- Rate limiting and user preference enforcement before queueing
- Retry patterns (exponential backoff) and DLQ for reliability
- Observability: metrics, logging, and alerting in a distributed system

---

## License

MIT — see [LICENSE](LICENSE)
