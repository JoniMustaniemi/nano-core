from __future__ import annotations

import pytest

from scripts.bump_version import (
    bump_patch,
    has_code_changes,
    read_version,
    write_version,
)


def test_read_and_write_version() -> None:
    content = '[project]\nname = "nano-core"\nversion = "0.1.17"\n'
    assert read_version(content) == "0.1.17"
    updated = write_version(content, "0.1.18")
    assert read_version(updated) == "0.1.18"


def test_bump_patch() -> None:
    assert bump_patch("0.1.17") == "0.1.18"
    assert bump_patch("1.0.9") == "1.0.10"


def test_bump_patch_rejects_invalid_format() -> None:
    with pytest.raises(ValueError):
        bump_patch("0.1")


def test_has_code_changes() -> None:
    assert has_code_changes(["app/main.py", "tests/test_main.py"]) is True
    assert has_code_changes(["README.md", "docs/guide.md"]) is False
    assert has_code_changes(["README.md", "app/main.py"]) is True
    assert has_code_changes(["pyproject.toml"]) is False
