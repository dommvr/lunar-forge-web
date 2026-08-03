import pytest

from lunar_forge_web.auth.supabase import JWTValidationError


@pytest.mark.asyncio
async def test_jwt_success(container, token_factory):
    claims = await container.jwt_verifier.verify(token_factory())

    assert claims.subject == "user-a"
    assert claims.assurance_level.value == "aal1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"issuer": "https://wrong.example/auth/v1"},
        {"audience": "wrong"},
        {"role": "service_role"},
        {"expires_delta": -60},
        {"kid": "unknown-key"},
    ],
)
async def test_jwt_rejects_untrusted_claims_or_keys(container, token_factory, overrides):
    with pytest.raises(JWTValidationError):
        await container.jwt_verifier.verify(token_factory(**overrides))
