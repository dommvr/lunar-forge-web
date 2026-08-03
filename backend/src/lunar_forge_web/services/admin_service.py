from lunar_forge_web.domain.models import AdminOverviewResponse


class AdminService:
    def empty_overview(self) -> AdminOverviewResponse:
        return AdminOverviewResponse(
            users_total=0,
            users_suspended=0,
            sandboxes_active=0,
            turns_today=0,
            estimated_cost_today_microusd=0,
            cleanup_failures=0,
            sandbox_kill_switch_enabled=False,
            owner_funded_enabled=False,
        )
