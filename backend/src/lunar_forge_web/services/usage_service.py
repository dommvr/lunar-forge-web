"""Owner-funded hard-limit orchestration."""

from __future__ import annotations

from datetime import date, datetime, timezone

from lunar_forge_web.domain.models import UsageSummary
from lunar_forge_web.security.limits import (
    OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD,
    OWNER_FUNDED_MAX_REASONING_EFFORT,
    OWNER_FUNDED_PROVIDER,
    OWNER_FUNDED_TURNS_PER_USER_PER_DAY,
    OWNER_FUNDED_TURN_TIMEOUT_SECONDS,
    OWNER_FUNDED_USER_DAILY_COST_MICROUSD,
)
from lunar_forge_web.storage.records import QuotaReservation, QuotaSnapshot, UsageRecord
from lunar_forge_web.storage.repositories import QuotaRepository


class UsageService:
    provider = OWNER_FUNDED_PROVIDER
    maximum_reasoning_effort = OWNER_FUNDED_MAX_REASONING_EFFORT
    turn_timeout_seconds = OWNER_FUNDED_TURN_TIMEOUT_SECONDS
    daily_turn_limit = OWNER_FUNDED_TURNS_PER_USER_PER_DAY
    daily_user_cost_limit_microusd = OWNER_FUNDED_USER_DAILY_COST_MICROUSD
    daily_global_cost_limit_microusd = OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD

    def __init__(self, repository: QuotaRepository | None = None) -> None:
        self._repository = repository

    def within_limits(self, summary: UsageSummary) -> bool:
        return (
            summary.turns < OWNER_FUNDED_TURNS_PER_USER_PER_DAY
            and summary.estimated_cost_microusd
            < OWNER_FUNDED_USER_DAILY_COST_MICROUSD
        )

    async def reserve(
        self,
        *,
        user_id: str,
        turn_id: str,
        maximum_estimated_cost_microusd: int | None = None,
        now: datetime | None = None,
    ) -> QuotaReservation:
        if self._repository is None:
            raise RuntimeError("Quota repository is unavailable.")
        return await self._repository.reserve_owner_funded_turn(
            user_id=user_id,
            turn_id=turn_id,
            reserved_cost_microusd=maximum_estimated_cost_microusd,
            now=now or datetime.now(timezone.utc),
        )

    async def settle(
        self,
        *,
        turn_id: str,
        actual_cost_microusd: int,
        input_tokens: int,
        output_tokens: int,
        sandbox_id: str | None,
        model: str,
        now: datetime | None = None,
    ) -> UsageRecord:
        if self._repository is None:
            raise RuntimeError("Quota repository is unavailable.")
        return await self._repository.settle_owner_funded_turn(
            turn_id=turn_id,
            actual_cost_microusd=actual_cost_microusd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            sandbox_id=sandbox_id,
            provider=OWNER_FUNDED_PROVIDER,
            model=model,
            now=now or datetime.now(timezone.utc),
        )

    async def release(
        self, turn_id: str, *, now: datetime | None = None
    ) -> None:
        if self._repository is None:
            raise RuntimeError("Quota repository is unavailable.")
        await self._repository.release_owner_funded_reservation(
            turn_id, now or datetime.now(timezone.utc)
        )

    async def snapshot(self, user_id: str, day: date) -> QuotaSnapshot:
        if self._repository is None:
            raise RuntimeError("Quota repository is unavailable.")
        return await self._repository.snapshot(user_id, day)
