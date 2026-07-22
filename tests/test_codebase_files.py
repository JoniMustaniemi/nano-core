from app.proactive.codebase_files import (
    file_content_hash,
    list_all_app_files,
    package_for_path,
    walk_app_files,
)


def test_list_all_app_files_includes_every_py_file(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app" / "api").mkdir(parents=True)
    (tmp_path / "app" / "tools").mkdir(parents=True)
    (tmp_path / "app" / "api" / "chat.py").write_text("# api\n", encoding="utf-8")
    (tmp_path / "app" / "tools" / "z_last.py").write_text("# tools\n", encoding="utf-8")

    paths = list_all_app_files()

    assert paths == ["app/api/chat.py", "app/tools/z_last.py"]


def test_walk_app_files_caps_results(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    for index in range(3):
        (tmp_path / "app" / f"module_{index}.py").write_text("x", encoding="utf-8")

    assert walk_app_files(max_files=2) == ["app/module_0.py", "app/module_1.py"]


def test_package_for_path() -> None:
    assert package_for_path("app/tools/pr_service.py") == "app/tools"


def test_file_content_hash_is_stable(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app").mkdir()
    target = tmp_path / "app" / "main.py"
    target.write_text("print('nano')\n", encoding="utf-8")

    first = file_content_hash("app/main.py")
    second = file_content_hash("app/main.py")

    assert first == second
    assert len(first) == 64
