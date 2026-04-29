import json
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis_client import get_redis
from models.models import UserPreference

logger = structlog.get_logger()

PREFS_CACHE_TTL = 300  # 5 minutes


def _cache_key(user_id: UUID) -> str:
    return f"user_prefs:{user_id}"


async def get_user_preferences(
    user_id: UUID, db: AsyncSession
) -> UserPreference | None:
    """Return preferences from Redis cache, falling back to PostgreSQL."""
    redis = await get_redis()
    key = _cache_key(user_id)

    cached = await redis.get(key)
    if cached:
        logger.debug("Preferences cache hit", user_id=str(user_id))
        data = json.loads(cached)
        # Reconstruct ORM object from cached dict
        prefs = UserPreference(**data)
        return prefs

    logger.debug("Preferences cache miss", user_id=str(user_id))
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()

    if prefs:
        await _cache_preferences(redis, key, prefs)

    return prefs


async def invalidate_preferences_cache(user_id: UUID):
    redis = await get_redis()
    await redis.delete(_cache_key(user_id))


async def _cache_preferences(redis, key: str, prefs: UserPreference):
    data = {
        "id": str(prefs.id),
        "user_id": str(prefs.user_id),
        "email_enabled": prefs.email_enabled,
        "sms_enabled": prefs.sms_enabled,
        "push_enabled": prefs.push_enabled,
        "inapp_enabled": prefs.inapp_enabled,
        "transactional": prefs.transactional,
        "promotional": prefs.promotional,
        "system_alerts": prefs.system_alerts,
        "max_promotional_per_day": prefs.max_promotional_per_day,
        "dnd_start_hour": prefs.dnd_start_hour,
        "dnd_end_hour": prefs.dnd_end_hour,
    }
    await redis.setex(key, PREFS_CACHE_TTL, json.dumps(data))


def is_channel_allowed(prefs: UserPreference, channel: str) -> bool:
    """Check if the user has the requested channel enabled."""
    return getattr(prefs, f"{channel}_enabled", True)


def is_type_allowed(prefs: UserPreference, notification_type: str) -> bool:
    """Check if the user has the notification type enabled."""
    mapping = {
        "transactional": prefs.transactional,
        "promotional": prefs.promotional,
        "system_alert": prefs.system_alerts,
    }
    return mapping.get(notification_type, True)


async def is_rate_limited(user_id: UUID, notification_type: str, max_per_day: int) -> bool:
    """Check promotional rate limit using a Redis counter (resets at midnight UTC)."""
    if notification_type != "promotional":
        return False

    redis = await get_redis()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"rate_limit:{user_id}:promotional:{today}"

    count = await redis.get(key)
    if count and int(count) >= max_per_day:
        logger.warning("Rate limit reached", user_id=str(user_id), count=count)
        return True

    # Increment counter; set TTL to 24h on first use
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)
    await pipe.execute()
    return False
