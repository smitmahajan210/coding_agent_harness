"""Validate user submissions and prepare disposable, per-run workspaces."""
from __future__ import annotations

import io
import stat
import zipfile
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

MAX_FILES = 40
MAX_FILE_BYTES = 100_000
MAX_TOTAL_BYTES = 500_000
MAX_UPLOAD_BYTES = 5_000_000
IGNORED = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "__MACOSX"}


def validate_path(name: str) -> str:
    path = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts:
        raise ValueError("Use relative file names without '..', drive letters, or backslashes.")
    if any(part.startswith(".") or part in IGNORED for part in path.parts):
        raise ValueError("Hidden files, environment files, and cache folders are not accepted.")
    if path.suffix != ".py" and path.as_posix() != "requirements.txt":
        raise ValueError("Add Python (.py) files, or a requirements.txt at the project root.")
    return path.as_posix()


def validate_files(files: dict[str, str]) -> dict[str, str]:
    if not files or not any(name.endswith(".py") for name in files):
        raise ValueError("Add at least one Python file to check.")
    if len(files) > MAX_FILES:
        raise ValueError(f"Please use a smaller project: at most {MAX_FILES} files.")
    total = 0
    normalized = {}
    seen = set()
    for name, content in files.items():
        name = validate_path(name)
        if name.casefold() in seen:
            raise ValueError(f"More than one file uses the name {name}.")
        seen.add(name.casefold())
        size = len(content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise ValueError(f"{name} is too large. Each file can be up to 100 KB.")
        if "\x00" in content:
            raise ValueError(f"{name} must be a text file.")
        total += size
        normalized[name] = content
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Please keep the total code size below 500 KB.")
    return normalized


def files_from_uploads(uploads: list[tuple[str, bytes]]) -> dict[str, str]:
    files: dict[str, str] = {}
    total = 0

    def add(name: str, data: bytes):
        nonlocal total
        name = validate_path(name)
        if name in files:
            raise ValueError(f"Duplicate file: {name}. Upload each file only once.")
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES or len(files) >= MAX_FILES:
            raise ValueError("Use at most 40 files, 100 KB per file, and 500 KB of code in total.")
        try:
            files[name] = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{name} must use UTF-8 text encoding.") from exc

    for name, data in uploads:
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Each upload must be smaller than 5 MB.")
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    for info in archive.infolist():
                        if info.is_dir():
                            continue
                        parts = PurePosixPath(info.filename).parts
                        # Reject unsafe paths even for entries we would otherwise skip.
                        if ".." in parts or info.filename.startswith("/") or "\\" in info.filename:
                            raise ValueError("The ZIP contains an unsafe file path.")
                        if stat.S_ISLNK(info.external_attr >> 16):
                            raise ValueError("ZIP files containing symbolic links are not supported.")
                        if any(p.startswith(".") or p in IGNORED for p in parts):
                            continue
                        if not info.filename.endswith(".py") and info.filename != "requirements.txt":
                            continue
                        if info.file_size > MAX_FILE_BYTES or total + info.file_size > MAX_TOTAL_BYTES:
                            raise ValueError("The ZIP contains too much code. Limit: 100 KB per file, 500 KB total.")
                        add(info.filename, archive.read(info))
            except (zipfile.BadZipFile, RuntimeError) as exc:
                raise ValueError("Upload a valid, unencrypted ZIP file.") from exc
        else:
            add(name, data)
    return validate_files(files)


def create_workspace(files: dict[str, str]) -> TemporaryDirectory:
    files = validate_files(files)
    workspace = TemporaryDirectory(prefix="code-harness-")
    try:
        for name, content in files.items():
            target = Path(workspace.name) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    except Exception:
        workspace.cleanup()
        raise
    return workspace


def workspace_zip(root: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                name = path.relative_to(root).as_posix()
                try:
                    validate_path(name)
                except ValueError:
                    continue
                archive.writestr(name, path.read_bytes())
    return buffer.getvalue()


def is_test_file(name: str) -> bool:
    path = PurePosixPath(name)
    return "tests" in path.parts or path.name == "conftest.py" or path.name.startswith("test_") or path.name.endswith("_test.py")
