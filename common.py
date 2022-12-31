import asyncio
from typing import Callable

import fakeredis._server as _redis
from sqlalchemy.future import Engine

redis: _redis.FakeStrictRedis


LOGIN = asyncio.Lock()

database: Engine

packet_handlers: dict[int, Callable] = {}
