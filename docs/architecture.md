# Architecture

## High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Clients / Services                    │
│         (e-commerce platform, marketing system, etc.)        │
└─────────────────────────┬───────────────────────────────────┘
                          │ POST /notifications
                          ▼
             ┌────────────────────────┐
             │   API Gateway /        │
             │   Notification Service │  ← JWT auth, rate limiting
             │   (FastAPI)            │
             └────────┬───────────────┘
                      │
          ┌───────────┼───────────────┐
          │           │               │
          ▼           ▼               ▼
   ┌─────────┐  ┌──────────┐  ┌────────────┐
   │  User   │  │Scheduler │  │  PostgreSQL │
   │ Prefs   │  │ Service  │  │  (metadata, │
   │ (Redis  │  │ (future  │  │   logs)     │
   │  cache) │  │  notifs) │  └────────────┘
   └─────────┘  └────┬─────┘
                     │ (on schedule trigger)
                     ▼
          ┌──────────────────────┐
          │      RabbitMQ        │
          │  ┌────────────────┐  │
          │  │  email queue   │  │
          │  │  sms queue     │  │
          │  │  push queue    │  │
          │  │  inapp queue   │  │
          │  │  dlq (failed)  │  │
          │  └────────────────┘  │
          └──────────────────────┘
                     │
     ┌───────────────┼───────────────────┐
     ▼               ▼                   ▼                   ▼
┌─────────┐    ┌──────────┐    ┌──────────────┐    ┌───────────────┐
│  Email  │    │   SMS    │    │     Push     │    │   In-App      │
│Processor│    │Processor │    │  Processor   │    │  Processor    │
│         │    │          │    │              │    │               │
│SendGrid │    │  Twilio  │    │     FCM      │    │  WebSocket    │
└────┬────┘    └────┬─────┘    └──────┬───────┘    └───────┬───────┘
     │              │                 │                     │
     └──────────────┴─────────────────┴─────────────────────┘
                                  │
                          ┌───────▼────────┐
                          │ notification_  │
                          │ logs (Postgres)│
                          └───────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Prometheus + Grafana        │
                    │  (metrics, dashboards)       │
                    └─────────────────────────────┘
```

---

## Component Descriptions

### Notification Service (FastAPI)
Entry point for all notification requests. Validates requests, checks user preferences via the cache, optionally routes to the Scheduler, then publishes messages to RabbitMQ.

### User Preference Service
Reads/writes user preferences from PostgreSQL; results cached in Redis. Enforces opt-in/out and daily rate limits per channel before a notification is queued.

### Scheduler Service
Stores future-dated notifications in the `scheduled_notifications` table (partitioned by `scheduled_at`). A cron loop polls for due notifications and publishes them to RabbitMQ.

### RabbitMQ
Acts as the buffer between ingestion and delivery. Separate queues per channel allow independent scaling. A Dead Letter Queue (DLQ) captures messages that exceed retry limits.

### Channel Processors
Each is a standalone service that consumes its queue and delivers via the appropriate provider. Implements exponential backoff retry and writes delivery status to `notification_logs`.

### PostgreSQL
Stores: users, notifications, notification_logs, user_preferences, scheduled_notifications.

### Redis
Caches user preferences to avoid hot-path DB reads on every notification dispatch.

### Prometheus + Grafana
Prometheus scrapes metrics from each service. Grafana dashboards visualize throughput, delivery latency, and failure rates per channel. Each service emits structured JSON logs via `structlog` (ready to forward to any log aggregator).

---

## Database Schema (Summary)

| Table | Purpose |
|-------|---------|
| `users` | User identity and basic info |
| `user_preferences` | Per-user channel opt-ins, rate limits |
| `notifications` | Core notification records |
| `notification_logs` | Delivery attempt history (status, timestamps) |
| `scheduled_notifications` | Future notifications pending delivery |

---

## Scalability Notes

- Each service is independently deployable and horizontally scalable
- RabbitMQ → Kafka migration path exists for >10K sustained msg/sec
- PostgreSQL tables partitioned by time for large-volume log queries
- Redis cluster mode available for preference cache at scale
- Multi-AZ PostgreSQL replication for 99.99% availability target
