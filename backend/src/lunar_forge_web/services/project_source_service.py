from lunar_forge_web.security.paths import normalize_workspace_path


class ProjectSourceService:
    def validate_destination(self, destination: str) -> str:
        return normalize_workspace_path(destination)
