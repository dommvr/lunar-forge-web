from lunar_forge_web.domain.models import AdminOverviewResponse, AdminSettingsResponse
from lunar_forge_web.storage.repositories import AdminSettingsRepository


class AdminService:
    def __init__(self, settings: AdminSettingsRepository | None = None) -> None:
        self._settings = settings

    def empty_overview(self) -> AdminOverviewResponse:
        return AdminOverviewResponse(
            users_total=0,
            users_suspended=0,
            sandboxes_active=0,
            turns_today=0,
            estimated_cost_today_microusd=0,
            cleanup_failures=0,
            sandbox_kill_switch_enabled=False,
            owner_funded_enabled=True,
        )

    async def get_settings(self) -> AdminSettingsResponse:
        if self._settings is None:
            return AdminSettingsResponse(
                sandbox_kill_switch_enabled=False,
                owner_funded_enabled=True,
            )
        record = await self._settings.get()
        return AdminSettingsResponse(
            sandbox_kill_switch_enabled=record.sandbox_kill_switch_enabled,
            owner_funded_enabled=record.owner_funded_enabled,
        )

    async def update_settings(
        self,
        *,
        sandbox_kill_switch_enabled: bool | None = None,
        owner_funded_enabled: bool | None = None,
    ) -> AdminSettingsResponse:
        if self._settings is None:
            raise RuntimeError("Admin settings repository is unavailable.")
        record = await self._settings.update(
            sandbox_kill_switch_enabled=sandbox_kill_switch_enabled,
            owner_funded_enabled=owner_funded_enabled,
        )
        return AdminSettingsResponse(
            sandbox_kill_switch_enabled=record.sandbox_kill_switch_enabled,
            owner_funded_enabled=record.owner_funded_enabled,
        )
