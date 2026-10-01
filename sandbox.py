"""Run submitted Python only in a fresh E2B sandbox, before and after review."""
from __future__ import annotations

import shlex
from pathlib import Path
from e2b import Sandbox
try:
    from e2b import CommandExitException
except ImportError:
    from e2b.exceptions import CommandExitException

from tools import _resolve_safe

SANDBOX_WORKDIR = "/home/user/workspace"
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".git"}


def run_checks_in_sandbox(workspace_root: Path, entrypoint: str = "", test_path: str | None = None) -> dict:
    """Syntax, discovered pytest tests, and an optional script; never execute locally."""
    if entrypoint:
        target = _resolve_safe(entrypoint, workspace_root)
        if not target.is_file() or target.suffix != ".py":
            raise ValueError("Choose an existing Python file to run.")
    python_files = [p for p in workspace_root.rglob("*.py") if not any(x in IGNORED_PARTS for x in p.parts)]
    has_tests = test_path is not None or any(
        p.name.startswith("test_") or p.name.endswith("_test.py") for p in python_files
    )
    checks = []
    sandbox = None
    stage = "setup"

    def result(passed: bool, summary: str, returncode: int = 0, infrastructure_error: bool = False):
        return {
            "passed": passed, "summary": summary, "returncode": returncode,
            "stdout": "\n\n".join(f"{c['name']}:\n{c['output']}" for c in checks)[-6000:],
            "checks": checks, "infrastructure_error": infrastructure_error,
            "scope": "tests" if has_tests else ("script" if entrypoint else "syntax"),
            "limitations": (
                "Passing these checks does not prove every possible input behaves correctly."
                if has_tests else
                "No tests were supplied. This checks Python syntax" +
                (" and one run of your script" if entrypoint else " only; functions were not exercised") +
                ". Expected results and other inputs remain unverified."
            ),
        }

    def command(name: str, cmd: str, timeout: int):
        try:
            proc = sandbox.commands.run(cmd, timeout=timeout)
            code, stdout, stderr = proc.exit_code, proc.stdout, proc.stderr
        except CommandExitException as exc:
            code, stdout, stderr = exc.exit_code, exc.stdout, exc.stderr
        output = (stdout + ("\n" + stderr if stderr else "")).strip()
        checks.append({"name": name, "passed": code == 0, "output": output[-4000:]})
        return code

    try:
        sandbox = Sandbox.create(timeout=300)
        sandbox.commands.run(f"mkdir -p {SANDBOX_WORKDIR}", timeout=10)
        for file in sorted(workspace_root.rglob("*")):
            if not file.is_file() or file.is_symlink() or any(p in IGNORED_PARTS for p in file.parts):
                continue
            sandbox.files.write(f"{SANDBOX_WORKDIR}/{file.relative_to(workspace_root)}", file.read_text())
        prefix = f"cd {SANDBOX_WORKDIR} && "
        stage = "syntax"
        code = command("Python syntax", prefix + "python -m compileall -q .", 30)
        if code:
            return result(False, "Python could not understand part of the code.", code)
        stage = "setup"
        if (workspace_root / "requirements.txt").is_file():
            code = command("Install project dependencies", prefix + "python -m pip install -q -r requirements.txt", 120)
            if code:
                return result(False, "The project's dependencies could not be installed.", code, True)
        if has_tests:
            code = command("Prepare test runner", "python -m pip install -q pytest", 120)
            if code:
                return result(False, "The test runner could not be installed.", code, True)
            stage = "tests"
            code = command("Existing tests", prefix + "python -m pytest " + shlex.quote(test_path or ".") + " -q", 90)
            if code:
                if code == 5:
                    return result(False, "No runnable tests were found. Check the uploaded test files.", code, True)
                return result(False, "The existing tests found a problem.", code)
        if entrypoint:
            stage = "script"
            code = command("Run your program", prefix + "python " + shlex.quote("./" + entrypoint) + " < /dev/null", 30)
            if code:
                return result(False, "The program stopped with an error.", code)
        return result(True, "All selected checks passed." if has_tests or entrypoint else "Python syntax checks passed.")
    except Exception as exc:
        checks.append({"name": stage, "passed": False, "output": f"{type(exc).__name__}: {exc}"[-2000:]})
        return result(False, "Checks could not finish. The sandbox may be unavailable or the program may need input or more time.", -1, True)
    finally:
        if sandbox:
            try:
                sandbox.kill()
            except Exception:
                pass


def run_pytest_in_sandbox(workspace_root: Path, test_path: str = "tests") -> dict:
    """Compatibility entry point for the terminal workflow."""
    return run_checks_in_sandbox(workspace_root, test_path=test_path)
