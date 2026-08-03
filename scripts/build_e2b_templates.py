"""Build versioned E2B templates without writing to the core checkout."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

from e2b import Template


WEB_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = WEB_ROOT / "e2b" / ".build"
CORE_RECORD = WEB_ROOT / "backend" / "core-source.json"
TEMPLATES = {
    "python-cli": WEB_ROOT / "e2b" / "templates" / "python-cli" / "template.py",
    "static-site": WEB_ROOT / "e2b" / "templates" / "static-site" / "template.py",
    "vite-react": WEB_ROOT / "e2b" / "templates" / "vite-react" / "template.py",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=sorted(TEMPLATES), action="append")
    args = parser.parse_args()
    core_root = _core_root()
    _verify_core_revision(core_root)
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=BUILD_ROOT, prefix="core-build-") as temp:
        core_wheel = _build_core_wheel(core_root, Path(temp))
        for name in args.only or list(TEMPLATES):
            module = _load_template(name, TEMPLATES[name])
            definition = module.create_template(core_wheel)
            result = Template.build(
                definition,
                alias=module.ALIAS,
                cpu_count=2,
                memory_mb=2_048,
            )
            print(f"built {name}: {result}")


def _core_root() -> Path:
    value = os.environ.get("LUNAR_FORGE_CORE_PATH")
    if not value:
        raise SystemExit("LUNAR_FORGE_CORE_PATH is required.")
    root = Path(value).resolve()
    if not (root / "pyproject.toml").is_file() or not (root / "lunar_forge").is_dir():
        raise SystemExit("LUNAR_FORGE_CORE_PATH is not a LunarForge source checkout.")
    return root


def _verify_core_revision(core_root: Path) -> None:
    record = json.loads(CORE_RECORD.read_text(encoding="utf-8"))
    command = [
        "git",
        "-c",
        f"safe.directory={core_root.as_posix()}",
        "-C",
        str(core_root),
    ]
    result = subprocess.run(
        [*command, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() != record["git_commit"]:
        raise SystemExit("Core revision differs from backend/core-source.json.")
    status = subprocess.run(
        [*command, "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout:
        raise SystemExit("Core checkout must be clean before building templates.")


def _build_core_wheel(core_root: Path, work: Path) -> Path:
    source = work / "source"
    wheel_dir = work / "wheel"
    source.mkdir()
    wheel_dir.mkdir()
    shutil.copy2(core_root / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(core_root / "README.md", source / "README.md")
    shutil.copytree(
        core_root / "lunar_forge",
        source / "lunar_forge",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".agent"),
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheel_dir),
            str(source),
        ],
        check=True,
    )
    wheels = list(wheel_dir.glob("lunar_forge-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one LunarForge wheel.")
    return wheels[0]


def _load_template(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"lfw_e2b_{name}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Could not load template definition: {name}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    main()
