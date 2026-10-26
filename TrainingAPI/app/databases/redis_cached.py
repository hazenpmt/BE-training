import json
from typing import Optional, Any, List

import redis.asyncio as redis

from app.utils.logger_utils import get_logger
from config import RedisConfig

logger = get_logger('Redis Cache')


class RedisCache:
    def __init__(self, connection_url: str = None):
        self.connection_url = connection_url

        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis"""
        self.client = redis.from_url(
            self.connection_url or RedisConfig.CONNECTION_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await self.client.ping()
        logger.info("Redis connected")

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            logger.info("Redis disconnected")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        value = await self.client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        """Set value in cache with expiration"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        await self.client.set(key, value, ex=expire)

    async def delete(self, key: str):
        """Delete key from cache"""
        await self.client.delete(key)

    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        keys = []
        async for key in self.client.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self.client.delete(*keys)

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return await self.client.exists(key) > 0

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter"""
        return await self.client.incrby(key, amount)

    async def rate_limit(self, key, window):
        # Increment and expiry must be atomic across concurrent workers.
        return await self.client.eval('''
            local count = redis.call('INCR', KEYS[1])
            if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            return {count, redis.call('TTL', KEYS[1])}
        ''', 1, key, window)

    async def expire(self, key: str, seconds: int):
        """Set expiration time"""
        await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get time to live"""
        return await self.client.ttl(key)

    async def push(self, queue_name: str, value: Any):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        await self.client.rpush(queue_name, value)

    async def pull(self, queue_name: str, batch_size: int = 1000):
        records = await self.client.lrange(queue_name, 0, batch_size - 1)
        if not records:
            return []

        await self.client.ltrim(queue_name, len(records), -1)
        return [json.loads(x) for x in records]

    async def reverse_pull(self, queue_name: str, records: List[Any]):
        for value in reversed(records):
            try:
                value = json.dumps(value)
            except (TypeError, ValueError):
                pass

            await self.client.lpush(queue_name, value)
