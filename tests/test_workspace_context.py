from app.tools.workspace_context import effective_workspace_root, workspace_override, workspace_root


def test_effective_workspace_root_uses_override(tmp_path) -> None:
    override = tmp_path / "worktree"
    override.mkdir()

    assert effective_workspace_root() == workspace_root()

    with workspace_override(override):
        assert effective_workspace_root() == override.resolve()

    assert effective_workspace_root() == workspace_root()


def test_workspace_override_resets_after_exception(tmp_path) -> None:
    override = tmp_path / "worktree"
    override.mkdir()

    try:
        with workspace_override(override):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert effective_workspace_root() == workspace_root()
