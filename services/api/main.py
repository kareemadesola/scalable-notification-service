from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from cache.redis_client import close_redis
from db.database import engine, Base
from queue.publisher import RabbitMQPublisher
from routers import notifications, users

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Notification Service")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.publisher = RabbitMQPublisher()
    await app.state.publisher.connect()
    logger.info("RabbitMQ publisher connected")
    yield
    # Shutdown
    await app.state.publisher.close()
    await close_redis()
    await engine.dispose()
    logger.info("Notification Service shut down")


app = FastAPI(
    title="Scalable Notification Service",
    description="Multi-channel notification service (email, SMS, push, in-app)",
    version="1.0.0",
    lifespan=lifespan,
)

# Prometheus metrics — exposes /metrics endpoint
Instrumentator().instrument(app).expose(app)

# Routers
app.include_router(notifications.router)
app.include_router(users.router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
