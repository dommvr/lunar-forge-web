"""Python CLI template with the pinned LunarForge core wheel."""

from pathlib import Path

from e2b import Template


ALIAS = "lfw-python-cli-v1"


def create_template(core_wheel: Path):
    return (
        Template()
        .from_base_image()
        .apt_install(["git", "zip", "unzip"])
        .copy(core_wheel, "/tmp/lunar-forge-core.whl")
        .run_cmd("python -m pip install --no-cache-dir /tmp/lunar-forge-core.whl")
        .run_cmd("rm -f /tmp/lunar-forge-core.whl")
        .make_dir("/home/user/project", user="user")
        .make_dir("/home/user/project/.lunar-forge/artifacts", user="user")
        .set_workdir("/home/user/project")
        .set_user("user")
    )
