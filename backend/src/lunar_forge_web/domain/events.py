"""Web transport mirror of the stable LunarForge core event envelope."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator

from lunar_forge_web.domain.base import ContractModel, Identifier


class AgentEventContract(ContractModel):
    schema_version: Literal[1] = 1
    event_id: Identifier
    session_id: Identifier
    turn_id: Identifier
    sequence: int = Field(ge=0)
    timestamp: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any]
    parent_event_id: Identifier | None = None

    @field_validator("payload")
    @classmethod
    def _bound_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            serialized = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Event payload must be JSON-safe.") from exc
        if len(serialized) > 100_000:
            raise ValueError("Event payload must not exceed 100,000 characters.")
        return payload
