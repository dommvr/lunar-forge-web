"""Cancellation and rollback report contract."""

from pydantic import Field

from lunar_forge_web.domain.base import ContractModel, SafePath


class RollbackReport(ContractModel):
    confirmed: bool
    reverted_paths: list[SafePath] = Field(default_factory=list, max_length=10_000)
    retained_paths: list[SafePath] = Field(default_factory=list, max_length=10_000)
    failed_paths: list[SafePath] = Field(default_factory=list, max_length=10_000)
