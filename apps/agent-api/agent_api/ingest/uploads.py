"""Helpers for managing uploaded files on disk.

Files live at data/uploads/<collection>/<safe-filename>. The path is
relative to the project root. We use the existing settings module to
locate the project root.
"""

import re
from pathlib import Path

from agent_api.settings import ENV_FILE


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
SUPPORTED_EXTENSIONS = {".md", ".pdf"}


# Filenames can be anything users type. Sanitize before using on disk.
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _project_root() -> Path:
    """Locate the project root. ENV_FILE is the .env at the project root."""
    if ENV_FILE is None:
        raise RuntimeError("ENV_FILE not resolved; cannot determine project root")
    return ENV_FILE.parent


def safe_filename(name: str) -> str:
    """Make a filename safe for the filesystem.

    Replace anything that isn't [A-Za-z0-9._-] with '_'. Collapse runs
    of underscores. Strip leading dots so we don't make hidden files.
    """
    cleaned = _SAFE_NAME_RE.sub("_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    return cleaned or "untitled"


def uploads_dir_for(collection: str) -> Path:
    """Return the absolute path to the uploads dir for a collection."""
    # Treat collection like a filename for safety.
    safe = safe_filename(collection)
    if safe != collection:
        raise ValueError(
            f"Collection name contains characters that aren't safe for disk: {collection!r}"
        )
    return _project_root() / "data" / "uploads" / collection


def save_upload(collection: str, filename: str, content: bytes) -> Path:
    """Save uploaded bytes to disk and return the absolute path.

    Validates extension and size before writing. Overwrites any existing
    file with the same name. Caller is responsible for collection
    existence and authorization.
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File too large: {len(content)} bytes (max {MAX_UPLOAD_BYTES})"
        )

    target_dir = uploads_dir_for(collection)
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_name = safe_filename(Path(filename).name)
    # Preserve the extension; safe_filename may have removed it
    if not safe_name.endswith(ext):
        safe_name = f"{safe_name}{ext}"

    target_path = target_dir / safe_name
    target_path.write_bytes(content)
    return target_path
