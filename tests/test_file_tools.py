from pathlib import Path

import pytest

from app.tools.files import list_files, read_text_file, resolve_workspace_path, write_text_file


def test_resolve_workspace_path_rejects_escape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.tools.workspace_context.get_settings",
        lambda: type("Settings", (), {"workspace_root": str(tmp_path)})(),
    )

    with pytest.raises(ValueError, match="within the workspace root"):
        resolve_workspace_path("../outside.txt")


def test_write_and_read_text_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.tools.workspace_context.get_settings",
        lambda: type("Settings", (), {"workspace_root": str(tmp_path)})(),
    )

    message = write_text_file("notes/demo.txt", "hello nano")
    content = read_text_file("notes/demo.txt")

    assert "wrote" in message
    assert content == "hello nano"
    assert Path(tmp_path / "notes" / "demo.txt").is_file()


def test_list_files_returns_sorted_names(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(
        "app.tools.workspace_context.get_settings",
        lambda: type("Settings", (), {"workspace_root": str(workspace)})(),
    )
    (workspace / "b.txt").write_text("b", encoding="utf-8")
    (workspace / "a.txt").write_text("a", encoding="utf-8")

    names = list_files(".")

    assert names == ["a.txt", "b.txt"]
