from pathlib import Path

from app.config import get_settings


def workspace_root() -> Path:
    return Path(get_settings().workspace_root).resolve()


def resolve_workspace_path(raw_path: str) -> Path:
    root = workspace_root()
    path = (root / raw_path).resolve()
    if root not in path.parents and path != root:
        raise ValueError("Path must stay within the workspace root.")
    return path


def read_text_file(raw_path: str) -> str:
    return resolve_workspace_path(raw_path).read_text(encoding="utf-8")


def write_text_file(raw_path: str, content: str) -> str:
    path = resolve_workspace_path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"wrote {path}"


def list_files(raw_path: str = ".") -> list[str]:
    path = resolve_workspace_path(raw_path)
    if not path.exists():
        return []
    return sorted(item.name for item in path.iterdir())
