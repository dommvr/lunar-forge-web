"""Structured redaction for logs and fake transport payloads."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any


REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?i)(authorization|cookie|password|passwd|secret|token|api[_-]?key|"
    r"credential|private[_-]?key|hidden[_-]?reasoning|chain[_-]?of[_-]?thought)"
)
_BEARER = re.compile(r"(?i)(bearer\s+)[^\s,;]+")
_KEY_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:api[_-]?key|token|secret|password|authorization)\s*[:=]\s*)"
    r"[^\s,;]+"
)
_PROVIDER_KEY = re.compile(
    r"(?i)\b(?:sk-(?:ant-)?|gh[pousr]_|github_pat_)[a-z0-9_-]{8,}\b"
)


def redact_text(value: str) -> str:
    redacted = _BEARER.sub(r"\1[REDACTED]", value)
    redacted = _KEY_ASSIGNMENT.sub(r"\1[REDACTED]", redacted)
    return _PROVIDER_KEY.sub(REDACTED, redacted)


def redact(value: Any, *, depth: int = 0) -> Any:
    if depth >= 12:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value[:50_000])
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 200:
                result["_truncated"] = True
                break
            safe_key = str(key)[:200]
            result[safe_key] = (
                REDACTED
                if _SENSITIVE_KEY.search(safe_key)
                else redact(item, depth=depth + 1)
            )
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact(item, depth=depth + 1) for item in list(value)[:200]]
    return f"[unsupported:{type(value).__name__}]"


class RedactingJsonFormatter(logging.Formatter):
    """Emit one bounded JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", {"message": record.getMessage()})
        payload = {
            "level": record.levelname.lower(),
            "logger": record.name,
            **redact(event),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingJsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
