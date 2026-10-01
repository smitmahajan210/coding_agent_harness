"""Read-only workspace tools and reviewable proposals, bound to a run's root."""
from __future__ import annotations

import difflib
import uuid
from pathlib import Path
from langchain_core.tools import tool

WORKSPACE_ROOT = Path(__file__).resolve().parent / "workspace"
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".git"}


def _resolve_safe(path: str, workspace_root: Path = WORKSPACE_ROOT) -> Path:
    root = workspace_root.resolve()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path {path!r} escapes the workspace.")
    return resolved


def workspace_tools(workspace_root: Path):
    # Capturing a root in each tool avoids changing global state between users.
    @tool
    def list_dir(path: str = ".") -> str:
        """List files and folders relative to the current workspace."""
        try:
            target = _resolve_safe(path, workspace_root)
            if not target.is_dir():
                return f"ERROR: {path!r} is not a directory."
            return "\n".join(
                f"{p.name}/" if p.is_dir() else p.name
                for p in sorted(target.iterdir()) if p.name not in IGNORED_PARTS
            ) or "(empty directory)"
        except (ValueError, OSError) as exc:
            return f"ERROR: {exc}"

    @tool
    def read_file(path: str) -> str:
        """Read a workspace file with line numbers. Errors start with ERROR:."""
        try:
            target = _resolve_safe(path, workspace_root)
            if not target.is_file():
                return f"ERROR: {path!r} does not exist."
            return "\n".join(f"{i}: {line}" for i, line in enumerate(target.read_text().splitlines(), 1))
        except (ValueError, OSError) as exc:
            return f"ERROR: {exc}"

    return list_dir, read_file


list_dir, read_file = workspace_tools(WORKSPACE_ROOT)


def build_file_diff(file_path: str, new_content: str, rationale: str, iteration: int,
                    workspace_root: Path = WORKSPACE_ROOT) -> dict:
    target = _resolve_safe(file_path, workspace_root)
    old_content = target.read_text() if target.is_file() else ""
    unified = "".join(difflib.unified_diff(
        old_content.splitlines(keepends=True), new_content.splitlines(keepends=True),
        fromfile=f"a/{file_path}", tofile=f"b/{file_path}",
    ))
    return {
        "diff_id": uuid.uuid4().hex[:8], "file_path": file_path,
        "unified_diff": unified or "(no changes)", "rationale": rationale,
        "old_content": old_content, "new_content": new_content,
        "proposed_at_iteration": iteration,
    }


@tool
def propose_edit(file_path: str, new_content: str, rationale: str) -> str:
    """Propose COMPLETE replacement file content for human approval, never write it.

    Explain in plain language what is broken, why this change helps, and any
    assumptions. Include ALL supported fixes for the file in one proposal, not
    one proposal per line. Use a relative Python file path and preserve tests.
    """
    return "Proposals must be submitted through the coder's review queue."


def list_workspace_tree(workspace_root: Path = WORKSPACE_ROOT) -> str:
    lines = []
    for path in sorted(workspace_root.rglob("*")):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        rel = path.relative_to(workspace_root)
        lines.append(f"{'  ' * (len(rel.parts) - 1)}{rel.name}{'/' if path.is_dir() else ''}")
    return "\n".join(lines) or "(empty workspace)"
