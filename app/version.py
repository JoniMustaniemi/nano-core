from importlib.metadata import PackageNotFoundError, version

from app.config import get_settings


def get_version() -> str:
    settings = get_settings()
    if settings.nano_version.strip():
        return settings.nano_version.strip()
    try:
        return version("nano-core")
    except PackageNotFoundError:
        return "0.0.0.dev"
