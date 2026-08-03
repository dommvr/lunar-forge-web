"""Expiry cleanup and 30-day retained-metadata reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from lunar_forge_web.runtime.base import RuntimeProvider, RuntimeSandbox
from lunar_forge_web.storage.redis import UpstashRedisStore
from lunar_forge_web.storage.repositories import CleanupRepository


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    claimed: int
    completed: int
    failed: int
    retained_rows_purged: int


class CleanupReconciliationService:
    def __init__(
        self,
        repository: CleanupRepository,
        runtime: RuntimeProvider,
        coordination: UpstashRedisStore,
    ) -> None:
        self._repository = repository
        self._runtime = runtime
        self._coordination = coordination

    async def run_once(
        self,
        *,
        now: datetime | None = None,
        claim_limit: int = 25,
        purge_limit: int = 250,
    ) -> ReconciliationReport:
        selected_now = now or datetime.now(timezone.utc)
        claims = await self._repository.claim_expired(selected_now, claim_limit)
        completed = 0
        failed = 0
        for claim in claims:
            try:
                reference = claim.sandbox.runtime_reference
                if reference is not None:
                    await self._runtime.terminate(
                        RuntimeSandbox(
                            provider=claim.sandbox.runtime_provider,
                            reference=reference,
                            workspace_root=(
                                "/home/user/project"
                                if claim.sandbox.runtime_provider == "e2b"
                                else "/workspace"
                            ),
                            sandbox_id=claim.sandbox.id,
                            owner_id=claim.sandbox.owner_id,
                            template_id=claim.sandbox.template_id,
                        )
                    )
                await self._coordination.clear_sandbox(
                    claim.sandbox.id, claim.session_ids
                )
                await self._repository.complete(claim, selected_now)
                completed += 1
            except Exception as exc:  # reconciliation records failures for retry
                result_code = type(exc).__name__[:200]
                await self._repository.fail(claim, result_code, selected_now)
                failed += 1
        purged = await self._repository.purge_retained(selected_now, purge_limit)
        return ReconciliationReport(
            claimed=len(claims),
            completed=completed,
            failed=failed,
            retained_rows_purged=purged,
        )
