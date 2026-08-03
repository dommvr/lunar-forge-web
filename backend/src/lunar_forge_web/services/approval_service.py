from lunar_forge_web.domain.enums import ApprovalStatus
from lunar_forge_web.domain.models import ApprovalResponse


class ApprovalStateError(ValueError):
    pass


class ApprovalService:
    def resolve(self, approval: ApprovalResponse, approved: bool) -> ApprovalResponse:
        if approval.status != ApprovalStatus.PENDING.value:
            raise ApprovalStateError("Only pending approvals may be resolved.")
        return approval.model_copy(
            update={
                "status": (
                    ApprovalStatus.APPROVED.value
                    if approved
                    else ApprovalStatus.DENIED.value
                )
            }
        )
