"""UI-neutral role and ownership decisions."""

from lunar_forge_web.domain.enums import AssuranceLevel, UserRole
from lunar_forge_web.domain.models import Principal


def can_access_owned_resource(principal: Principal, owner_id: str) -> bool:
    return not principal.suspended and principal.id == owner_id


def is_mfa_verified_admin(principal: Principal) -> bool:
    return (
        not principal.suspended
        and principal.role == UserRole.ADMIN.value
        and principal.assurance_level == AssuranceLevel.AAL2.value
    )
