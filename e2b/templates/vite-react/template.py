"""Vite and React workspace with dependencies installed at template build."""

from pathlib import Path

from e2b import Template


ALIAS = "lfw-vite-react-v1"


def create_template(core_wheel: Path):
    del core_wheel  # The agent/core stays in the worker for frontend projects.
    template_dir = Path(__file__).parent
    return (
        Template()
        .from_base_image()
        .apt_install(["git", "zip", "unzip"])
        .make_dir("/home/user/project", user="user")
        .make_dir("/home/user/project/.lunar-forge/artifacts", user="user")
        .copy(template_dir / "starter", "/home/user/project", user="user")
        .set_workdir("/home/user/project")
        .run_cmd("npm ci --ignore-scripts --no-audit --no-fund", user="user")
        .set_user("user")
    )
