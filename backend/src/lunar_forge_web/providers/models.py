from typing import Literal

from lunar_forge_web.domain.base import ContractModel, Identifier


class ProviderSelection(ContractModel):
    provider: Literal["openai", "anthropic"]
    model: Identifier
