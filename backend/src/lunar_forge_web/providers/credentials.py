"""Per-turn model construction without environment or persistence mutation."""

from dataclasses import dataclass

from lunar_forge import ModelClient, create_ephemeral_model_client

from lunar_forge_web.config import Settings
from lunar_forge_web.domain.enums import FundingMode
from lunar_forge_web.domain.models import WorkerTurnRequest


@dataclass(frozen=True, slots=True, repr=False)
class EphemeralProviderCredential:
    value: str

    def __repr__(self) -> str:
        return "EphemeralProviderCredential([REDACTED])"


def create_turn_model_client(
    request: WorkerTurnRequest,
    settings: Settings,
) -> ModelClient:
    """Create one credential-bearing client and return no reusable secret state."""

    funding_mode = str(request.settings.funding_mode)
    if funding_mode == FundingMode.OWNER_FUNDED.value:
        if request.provider_credential is not None:
            raise ValueError("Owner-funded turns must not include a browser credential.")
        configured = settings.owner_funded_api_key
        if configured is None or not configured.get_secret_value():
            raise RuntimeError("The owner-funded model secret is unavailable.")
        credential = EphemeralProviderCredential(configured.get_secret_value())
        model = settings.owner_funded_model
        api = "responses"
    elif funding_mode == FundingMode.BYOK.value:
        if request.provider_credential is None:
            raise ValueError("BYOK turns require a credential in the current request.")
        credential = EphemeralProviderCredential(
            request.provider_credential.get_secret_value()
        )
        if request.settings.provider == "openai":
            model = settings.byok_openai_model
            api = "responses"
        else:
            model = settings.byok_anthropic_model
            api = "chat"
    else:
        raise ValueError("Unsupported funding mode.")

    return create_ephemeral_model_client(
        model=model,
        api_key=credential.value,
        api=api,
        reasoning_effort=str(request.settings.reasoning_effort),
    )
