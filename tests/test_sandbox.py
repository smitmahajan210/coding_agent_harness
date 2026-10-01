from types import SimpleNamespace

import pytest
import sandbox


@pytest.fixture
def fake_sandbox(monkeypatch):
    commands = []
    uploaded = {}
    killed = []
    def run(command, timeout):
        commands.append(command)
        return SimpleNamespace(exit_code=0, stdout="ok", stderr="")
    instance = SimpleNamespace(
        commands=SimpleNamespace(run=run),
        files=SimpleNamespace(write=lambda path, content: uploaded.update({path: content})),
        kill=lambda: killed.append(True),
    )
    monkeypatch.setattr(sandbox, "Sandbox", SimpleNamespace(create=lambda **kw: instance))
    return instance, commands, uploaded, killed


def test_syntax_only_does_not_execute_program_and_reports_limit(tmp_path, fake_sandbox):
    (tmp_path / "library.py").write_text("def value(): return 1")
    result = sandbox.run_checks_in_sandbox(tmp_path)
    _, commands, uploaded, killed = fake_sandbox
    assert result["passed"] and result["scope"] == "syntax"
    assert "functions were not exercised" in result["limitations"]
    assert not any("pytest" in cmd or "python library.py" in cmd for cmd in commands)
    assert list(uploaded) == ["/home/user/workspace/library.py"]
    assert killed


def test_existing_tests_and_selected_script_are_checked(tmp_path, fake_sandbox):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "test_main.py").write_text("assert True")
    result = sandbox.run_checks_in_sandbox(tmp_path, "main.py")
    _, commands, _, killed = fake_sandbox
    assert result["passed"] and result["scope"] == "tests"
    assert any("python -m pytest . -q" in cmd for cmd in commands)
    assert any("main.py < /dev/null" in cmd for cmd in commands)
    assert killed


def test_syntax_failure_is_reported_before_script_execution(tmp_path, fake_sandbox):
    (tmp_path / "main.py").write_text("print(")
    instance, commands, _, killed = fake_sandbox
    def run(command, timeout):
        commands.append(command)
        return SimpleNamespace(exit_code=1 if "compileall" in command else 0,
                               stdout="SyntaxError: '(' was never closed", stderr="")
    instance.commands.run = run
    result = sandbox.run_checks_in_sandbox(tmp_path, "main.py")
    assert not result["passed"] and not result["infrastructure_error"]
    assert "SyntaxError" in result["stdout"]
    assert not any("main.py <" in cmd for cmd in commands)
    assert killed


def test_connection_failure_is_not_reported_as_code_failure(tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text("print('hello')")
    def unavailable(**kwargs):
        raise ConnectionError("service unavailable")
    monkeypatch.setattr(sandbox, "Sandbox", SimpleNamespace(create=unavailable))
    result = sandbox.run_checks_in_sandbox(tmp_path)
    assert result["infrastructure_error"]
    assert not result["passed"]


def test_entrypoint_cannot_escape_workspace(tmp_path, fake_sandbox):
    with pytest.raises(ValueError, match="escapes"):
        sandbox.run_checks_in_sandbox(tmp_path, "../outside.py")
    assert not fake_sandbox[1]
