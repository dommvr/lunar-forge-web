"""Future coordination boundary; no Redis client is used in this phase."""

from typing import Protocol


class EventStreamStore(Protocol):
    async def append(self, stream_key: str, sequence: int, payload: str) -> None: ...
    async def replay(self, stream_key: str, after_sequence: int, limit: int) -> tuple[str, ...]: ...
