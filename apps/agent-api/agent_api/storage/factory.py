"""Factory that picks a storage backend based on settings."""

from pathlib import Path

from agent_api.settings import settings
from agent_api.storage.backends.sqlite import SQLiteStorage
from agent_api.storage.interfaces import Storage


def make_storage() -> Storage:
    """Return a Storage instance configured for the current backend."""
    backend = settings.storage_backend.lower()
    if backend == "sqlite":
        # Resolve the SQLite path relative to the project root if it isn't absolute
        sqlite_path = settings.sqlite_path
        if not Path(sqlite_path).is_absolute():
            # The settings.py module's ENV_FILE points at project_root/.env
            from agent_api.settings import ENV_FILE
            if ENV_FILE is not None:
                sqlite_path = str(ENV_FILE.parent / sqlite_path.lstrip("./"))
        return SQLiteStorage(db_path=sqlite_path)
    raise ValueError(f"Unknown storage backend: {backend}")
