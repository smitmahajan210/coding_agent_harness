import io
import zipfile
from pathlib import Path

import pytest

from uploads import create_workspace, files_from_uploads, validate_files, workspace_zip
from tools import workspace_tools, build_file_diff


def zipped(files):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return data.getvalue()


@pytest.mark.parametrize("name", ["../escape.py", "/tmp/escape.py", "a/../../escape.py", "a\\escape.py", ".env", "C:/escape.py"])
def test_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        validate_files({name: "print('hello')"})


def test_zip_preserves_project_structure_and_skips_secrets():
    result = files_from_uploads([("project.zip", zipped({
        "app/main.py": "print('hello')", "tests/test_main.py": "assert True",
        ".env": "SECRET=never-upload", "README.md": "readme",
        "requirements.txt": "requests==2.34.2",
    }))])
    assert set(result) == {"app/main.py", "tests/test_main.py", "requirements.txt"}


def test_zip_path_traversal_is_rejected():
    with pytest.raises(ValueError, match="unsafe"):
        files_from_uploads([("project.zip", zipped({"../main.py": "pass"}))])


def test_large_compressed_file_is_rejected():
    with pytest.raises(ValueError, match="too much code"):
        files_from_uploads([("project.zip", zipped({"main.py": "a" * 100_001}))])


def test_duplicate_and_invalid_text_files_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        files_from_uploads([("main.py", b"pass"), ("main.py", b"pass")])
    with pytest.raises(ValueError, match="UTF-8"):
        files_from_uploads([("main.py", b"\xff")])
    with pytest.raises(ValueError, match="one file"):
        validate_files({"main.py": "pass", "MAIN.py": "pass"})


def test_workspaces_and_tools_are_isolated_and_proposals_do_not_write():
    with create_workspace({"main.py": "print('one')"}) as first, create_workspace({"main.py": "print('two')"}) as second:
        _, read_first = workspace_tools(Path(first))
        _, read_second = workspace_tools(Path(second))
        assert "one" in read_first.invoke({"path": "main.py"})
        assert "two" in read_second.invoke({"path": "main.py"})
        assert read_first.invoke({"path": "../main.py"}).startswith("ERROR")
        proposal = build_file_diff("main.py", "print('fixed')", "Reason", 0, Path(first))
        assert proposal["old_content"] == "print('one')"
        assert Path(first, "main.py").read_text() == "print('one')"
        with zipfile.ZipFile(io.BytesIO(workspace_zip(Path(first)))) as z:
            assert z.read("main.py") == b"print('one')"
