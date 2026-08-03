"""Workspace-relative path validation used by future file services."""

from pathlib import PurePosixPath


class UnsafePathError(ValueError):
    pass


def normalize_workspace_path(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise UnsafePathError("Path is invalid.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafePathError("Path must remain inside the workspace.")
    return path.as_posix()
