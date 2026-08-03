from lunar_forge_web.domain.models import UsageSummary


class UsageService:
    def within_limits(self, summary: UsageSummary) -> bool:
        return (
            summary.turns < summary.daily_turn_limit
            and summary.estimated_cost_microusd < summary.daily_cost_limit_microusd
        )
