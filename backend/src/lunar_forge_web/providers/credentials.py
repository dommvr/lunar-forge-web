"""Ephemeral credential wrapper that never serializes its value."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, repr=False)
class EphemeralProviderCredential:
    value: str

    def __repr__(self) -> str:
        return "EphemeralProviderCredential([REDACTED])"
