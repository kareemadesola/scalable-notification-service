# Troubleshooting Log

A running record of every bug hit during development/testing, its root cause, and how it was fixed.

---

## 1. Docker build failed — `COPY ../shared` not found

**Error**
```
"/shared": not found
```

**Root cause**
`COPY ../shared /app/shared` in the processor Dockerfiles tried to copy a directory *above* the build context. Docker does not allow crossing the build context boundary — it only sees files within the folder you point it at.

**Fix**
Changed the build context from each processor's own subfolder (`./services/email_processor`) to the parent `./services/` folder in `docker-compose.yml`. Updated the `COPY` paths inside the Dockerfiles accordingly so they work relative to `services/`.

---

## 2. Port 5672 already in use (RabbitMQ)

**Error**
```
failed to bind host port 0.0.0.0:5672/tcp: address already in use
```

**Root cause**
A local RabbitMQ + Erlang installation was installed on the host machine. When Docker tried to bind port 5672, the local process was already holding it.

**Fix**
Uninstalled the local RabbitMQ and Erlang packages entirely:
```bash
sudo apt-get purge -y rabbitmq-server erlang*
sudo apt-get autoremove -y
```
> `apt-get purge` removes the package *and* its config files. `autoremove` cleans up dependencies that are no longer needed.

---

## 3. Port 5432 already in use (PostgreSQL)

**Error**
```
failed to bind host port 0.0.0.0:5432/tcp: address already in use
```

**Root cause**
Same pattern as above — a local PostgreSQL service was running on the host.

**Fix**
Stopped the local service:
```bash
sudo systemctl stop postgresql
sudo systemctl disable postgresql
```
> `systemctl stop` stops it immediately. `disable` prevents it from auto-starting on next reboot.

---

## 4. RabbitMQ health check failing despite successful startup

**Error**
```
Container ns_rabbitmq  unhealthy
dependency failed to start: container ns_rabbitmq is unhealthy
```

**Root cause — part 1 (timeout too short)**
RabbitMQ took ~87 seconds to fully boot. The health check config `interval: 10s, retries: 5` only waited a maximum of 50 seconds before declaring the container unhealthy.

**Fix — part 1**
Added `start_period: 90s` to give RabbitMQ time to boot before the retry counter starts counting. Also increased `retries` to `10`.

**Root cause — part 2 (command timeout)**
The health check command `rabbitmq-diagnostics ping` itself was taking over 5 seconds to respond, exceeding the `timeout: 5s` setting.

**Fix — part 2**
- Added `-q` (quiet) flag to reduce output overhead
- Increased `timeout` from `5s` to `15s`

Final config in `docker-compose.yml`:
```yaml
healthcheck:
  test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
  interval: 15s
  timeout: 15s
  retries: 10
  start_period: 90s
```

---

## 5. `inapp_service` crash — DNS resolution failure on startup

**Error**
```
socket.gaierror: [Errno -3] Temporary failure in name resolution
```

**Root cause**
The `inapp_service` container was caught in a restart loop from a previous failure. When it restarted, Docker's embedded DNS hadn't finished wiring up the new container instance before `asyncpg.create_pool()` was called — with zero retry logic, any transient failure caused an immediate crash.

**Fix**
Added an exponential backoff retry loop around `asyncpg.create_pool()` in the lifespan startup:
```python
for attempt in range(1, 11):
    try:
        app.state.db_pool = await asyncpg.create_pool(DATABASE_URL, ...)
        break
    except Exception as exc:
        logger.warning("DB connection failed, retrying", attempt=attempt, error=str(exc))
        if attempt == 10:
            raise
        await asyncio.sleep(attempt * 2)
```

---

## 6. `api` crash — `ModuleNotFoundError: No module named 'queue.publisher'`

**Error**
```
ModuleNotFoundError: No module named 'queue.publisher'; 'queue' is not a package
```

**Root cause**
Python has a built-in standard library module called `queue`. The project had a folder also named `queue/` inside `services/api/`. When Python resolved `from queue.publisher import ...`, it found its own built-in module first and failed.

**Fix**
Renamed the folder from `queue/` to `mq/` and updated the import in `main.py`:
```python
# Before
from queue.publisher import RabbitMQPublisher
# After
from mq.publisher import RabbitMQPublisher
```

**Lesson**
Avoid naming your own modules/packages with the same name as Python built-ins (`queue`, `asyncio`, `json`, `io`, `os`, `re`, etc.).

---

## 7. `api` crash — SQLAlchemy `metadata` reserved attribute

**Error**
```
sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.
```

**Root cause**
SQLAlchemy's `DeclarativeBase` uses `metadata` internally as a class-level attribute (`Base.metadata`) to track table definitions. Defining a column named `metadata` on a model overrides this internal attribute and breaks the ORM.

**Fix**
Renamed the Python attribute to `extra_data` while keeping the actual database column name as `metadata` using SQLAlchemy's explicit column name syntax:
```python
# Before
metadata = Column(JSONB)

# After
extra_data = Column("metadata", JSONB)
#                   ^^^^^^^^^
#                   tells SQLAlchemy the DB column is still called "metadata"
#                   but the Python attribute is "extra_data"
```
Updated all references across `models.py`, `schemas/notification.py`, `services/notification_service.py`, and `routers/notifications.py`.

---

## 8. `api` crash — structlog `PrintLogger` has no `.name` attribute

**Error**
```
AttributeError: 'PrintLogger' object has no attribute 'name'
```

**Root cause**
`logging_config.py` configured structlog with `logger_factory=structlog.PrintLoggerFactory()`. This creates `PrintLogger` instances — structlog's own minimal logger type. However, the processor chain included `structlog.stdlib.add_logger_name`, which reads `logger.name` — a property that only exists on Python's stdlib `logging.Logger`, not on `PrintLogger`.

**Fix**
Switched to `structlog.stdlib.LoggerFactory()` which creates proper stdlib logger wrappers:
```python
# Before
logger_factory=structlog.PrintLoggerFactory(),

# After
logger_factory=structlog.stdlib.LoggerFactory(),
```

---

## 9. `api` health check — `curl` not found in slim image

**Error**
```
Container ns_api  unhealthy
```

**Root cause**
The api health check used `curl -f http://localhost:8000/health`. `curl` is not installed in `python:3.12-slim` — the slim image strips out everything except Python and its standard library to keep image size small.

**Fix**
Switched to Python's built-in `urllib` which is always available in any Python container:
```yaml
# Before
test: ["CMD", "curl", "-f", "http://localhost:8000/health"]

# After
test: ["CMD-SHELL", "python3 -c 'import urllib.request; urllib.request.urlopen(\"http://localhost:8000/health\")'"]
```

**Lesson**
When writing Docker health checks for slim/alpine images, avoid assuming standard tools like `curl` or `wget` are present. Use whatever runtime the image already ships with — for Python images that means `python3 -c`.

---

## 10. `api` health check — YAML string corruption (duplicate text)

**Error**
```
SyntaxError: invalid syntax
# actual command seen by Docker:
import urllib.request; urllib.request.urlopen('...')llib.request.urlopen('...')
```

**Root cause**
When using the `["CMD", "python3", "-c", "..."]` YAML list form, the single-quoted Python string inside double-quoted YAML caused the editor to corrupt the value — part of the string was duplicated on save.

**Fix**
Switched to `CMD-SHELL` form with swapped quoting — outer double quotes for YAML, inner single quotes for the shell, and escaped double quotes for Python string delimiters:
```yaml
test: ["CMD-SHELL", "python3 -c 'import urllib.request; urllib.request.urlopen(\"http://localhost:8000/health\")'"]
```

**Lesson**
`CMD` form passes each element as a separate argument (no shell involved). `CMD-SHELL` passes the whole string to `/bin/sh -c`, which gives you full shell quoting control. When your command contains quotes, `CMD-SHELL` is easier to reason about.

---

## 11. `api` — `NotificationResponse.metadata` receives `MetaData()` object

**Error**
```
fastapi.exceptions.ResponseValidationError:
  {'type': 'dict_type', 'loc': ('response', 'metadata'), 'msg': 'Input should be a valid dictionary', 'input': MetaData()}
```

**Root cause**
`NotificationResponse` had a field named `metadata`. SQLAlchemy's `DeclarativeBase` attaches a class-level `metadata` attribute (a `MetaData()` object used to track table definitions) to every model. When Pydantic serialized the `Notification` ORM object using `from_attributes=True`, it picked up `Base.metadata` instead of the column value.

**Fix**
Renamed the response schema field from `metadata` to `extra_data` to match the model attribute rename done in issue #7.

---

## 12. `api` — `MissingGreenlet` error on `updated_at` during response serialization

**Error**
```
MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.
```

**Root cause**
`updated_at` is set by a DB server-side trigger on insert/update. After `db.flush()`, SQLAlchemy marks the column as "expired" — it will be lazily loaded on next access. But FastAPI serializes the response *before* the session commits and closes, so when Pydantic tried to access `notification.updated_at`, SQLAlchemy attempted an async DB call outside the async context.

**Fix**
Added `await db.refresh(notification)` after every `db.flush()` call. `refresh()` does an explicit `SELECT` to reload all server-side columns (like `updated_at`, `created_at`) while the session is still open and the async context is active.

---

## 13. `email_processor` — `ForeignKeyViolationError` on `notification_logs`

**Error**
```
asyncpg.exceptions.ForeignKeyViolationError: insert or update on table "notification_logs"
violates foreign key constraint "notification_logs_notification_id_fkey"
DETAIL: Key (notification_id)=(X) is not present in table "notifications".
```

**Root cause**
A race condition between the API and the processor:
1. API publishes message to RabbitMQ queue
2. API then updates `notification.status = queued` and calls `db.flush()`
3. DB session commits *after* the route returns (in `get_db()`)
4. The processor consumes the RabbitMQ message almost instantly and tries to insert a `notification_log` row referencing the notification
5. But the notification row hasn't been committed to the DB yet → FK violation

**Fix**
Moved the DB commit to *before* the RabbitMQ publish in the router. The sequence is now:
1. `notification.status = queued`
2. `await db.flush()`
3. `await db.commit()` ← commit first so the row is visible to other services
4. `await db.refresh(notification)` ← reload columns
5. `await publisher.publish(...)` ← only now publish to RabbitMQ

**Lesson**
In any system where a message queue triggers work that reads from the DB, always commit the DB transaction before publishing the message. Otherwise you create a race condition where the consumer sees the message before the data it references exists.

---

## 14. `api` startup — no retry on DB / RabbitMQ connection

**Root cause**
Even with `depends_on: condition: service_healthy` in Docker Compose, there can be a small window between a dependency passing its health check and being fully ready to accept connections. With no retry logic, the first connection attempt could fail and crash the app.

**Fix**
Added exponential backoff retry loops in `main.py` lifespan for both the DB schema creation and RabbitMQ publisher connection — up to 5 attempts with increasing sleep intervals (2s, 4s, 6s, 8s, 10s).

---

## 15. Scheduler crash — `ValueError: dictionary update sequence element #0 has length 1; 2 is required`

**Symptom**
`ns_scheduler` container enters a crash-restart loop immediately after processing its first due notification.

**Root cause**
The `metadata` column is stored as `TEXT` (JSON string) in PostgreSQL. When fetched via a raw `asyncpg` query, `row["metadata"]` is a plain Python `str`. Passing a string to `dict()` tries to iterate its characters as `(key, value)` pairs, which fails for any string longer than 1 character.

```python
# broken
"metadata": dict(row["metadata"]) if row["metadata"] else {}
```

**Fix**
Use `json.loads()` to deserialise the string first, with a fallback to `dict()` for cases where the driver returns an already-mapped object:

```python
"metadata": (json.loads(row["metadata"]) if isinstance(row["metadata"], str) else dict(row["metadata"])) if row["metadata"] else {}
```

**Lesson**
When reading JSON columns via raw SQL drivers (asyncpg, psycopg2), always deserialise with `json.loads()` — not `dict()`. ORM models handle this automatically, but raw `Row` objects do not.
