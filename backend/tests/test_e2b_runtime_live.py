from __future__ import annotations

import os
from uuid import uuid4

import pytest

from lunar_forge_web.runtime.e2b_provider import E2BRuntimeProvider


@pytest.mark.live_e2b
async def test_live_e2b_create_command_file_and_delete_smoke():
    api_key = os.environ.get("E2B_API_KEY")
    template = os.environ.get("LUNAR_FORGE_WEB_E2B_LIVE_TEMPLATE")
    if not api_key or not template:
        pytest.skip("E2B_API_KEY and LUNAR_FORGE_WEB_E2B_LIVE_TEMPLATE are required.")

    sandbox_id = f"sandbox_live_{uuid4().hex}"
    provider = E2BRuntimeProvider(
        api_key=api_key,
        template_ids={"python-cli": template},
    )
    runtime = await provider.create(
        owner_id="live-test", sandbox_id=sandbox_id, template_id="python-cli"
    )
    try:
        status = await provider.status(runtime)
        assert status.state == "running"
        assert status.secure_access is True
        assert status.internet_access is False
        command = await provider.run_command(
            runtime,
            "printf 'live e2b' > smoke.txt",
            timeout_seconds=30,
        )
        assert command.exit_code == 0
        content = await provider.read_file(runtime, "smoke.txt")
        assert content.content == "live e2b"
    finally:
        await provider.terminate(runtime)
