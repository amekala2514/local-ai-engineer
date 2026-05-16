"""In-memory session store.

Sessions are simple: a session ID maps to a creation timestamp.
That's enough for a single-user local app. When we add real users,
this expands to track user identity, but the interface stays the same.

For now, sessions are lost on server restart - users re-login.
If that becomes annoying, swap this for a SQLite-backed store.
"""

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


# Sessions are valid for 7 days. Adjust as needed.
SESSION_LIFETIME = timedelta(days=7)


@dataclass
class Session:
    """A single authenticated session."""

    id: str
    created_at: datetime
    expires_at: datetime


class InMemorySessionStore:
    """Trivial dict-backed session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        """Create a new session and return it."""
        now = datetime.now(timezone.utc)
        sid = secrets.token_urlsafe(32)
        session = Session(
            id=sid,
            created_at=now,
            expires_at=now + SESSION_LIFETIME,
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Return a session if it exists and isn't expired, else None."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if datetime.now(timezone.utc) >= session.expires_at:
            self._sessions.pop(session_id, None)
            return None
        return session

    def delete(self, session_id: str) -> None:
        """Invalidate a session."""
        self._sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        now = datetime.now(timezone.utc)
        expired = [sid for sid, s in self._sessions.items() if now >= s.expires_at]
        for sid in expired:
            self._sessions.pop(sid, None)
        return len(expired)


# A single shared instance
session_store = InMemorySessionStore()
