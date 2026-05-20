"""Brave Search API client.

This module wraps the Brave Search API for use by /api/search. It is
intentionally narrow: one function (search) that sends a query and
returns sanitized result snippets.

The module does NOT enforce rate limits, write audit records, or check
auth — those concerns live in the endpoint layer (main.py) so that
limits apply uniformly regardless of caller.

Defenses applied here:
- API key never appears in raised exceptions or returned errors
- httpx timeout caps request duration
- Response descriptions sanitized via sanitize_plain (strips HTML
  tags like <strong> that Brave wraps match terms in)
- Result count capped at search_result_count
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from agent_api.settings import settings
from agent_api.web.sanitizer import sanitize_html, sanitize_plain


BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
MAX_DESCRIPTION_CHARS = 400  # generous cap, snippets are ~200 chars typically


@dataclass
class SearchResultItem:
    """One web search result, sanitized and ready for prompt construction."""
    title: str
    url: str
    description: str  # sanitized plain text


@dataclass
class SearchResponse:
    """Aggregate response from a search call."""
    query: str            # the query as Brave echoed it back (after spellcheck)
    results: list[SearchResultItem]


class SearchError(Exception):
    """Raised when search fails for any reason.

    The exception message NEVER contains the API key. Callers can safely
    surface this message to clients.
    """


def _strip_key_from_error(exc: Exception, key: str) -> str:
    """Build an error message that doesn't leak the API key."""
    msg = f"{type(exc).__name__}: {exc}"
    if key and key in msg:
        msg = msg.replace(key, "<redacted>")
    return msg


async def search(query: str) -> SearchResponse:
    """Call Brave Search and return sanitized results.

    Args:
        query: the search query string (1-400 chars per Brave's limits)

    Returns:
        SearchResponse with up to settings.search_result_count items.

    Raises:
        SearchError: on any failure (network, auth, parse error, etc.).
            The error message is safe to surface — never contains the API key.
    """
    if not settings.brave_api_key:
        raise SearchError("Brave Search not configured: BRAVE_API_KEY missing")
    if not query or not query.strip():
        raise SearchError("Query is empty")
    if len(query) > 400:
        raise SearchError("Query exceeds 400 characters")

    key = settings.brave_api_key
    timeout = httpx.Timeout(settings.search_timeout_seconds)

    params = {
        "q": query.strip(),
        "count": min(settings.search_result_count, 20),
        "safesearch": "moderate",
        "country": "us",
        "search_lang": "en",
    }
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": key,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(BRAVE_ENDPOINT, params=params, headers=headers)
    except httpx.TimeoutException:
        raise SearchError(f"Brave Search timed out after {settings.search_timeout_seconds}s")
    except httpx.RequestError as e:
        raise SearchError(f"Network error contacting Brave Search: {_strip_key_from_error(e, key)}")

    if response.status_code == 401:
        raise SearchError("Brave Search authentication failed (check BRAVE_API_KEY)")
    if response.status_code == 429:
        raise SearchError("Brave Search rate limit exceeded (provider-side, not local limit)")
    if response.status_code >= 400:
        raise SearchError(f"Brave Search returned HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as e:
        raise SearchError(f"Brave Search returned invalid JSON: {_strip_key_from_error(e, key)}")

    # Brave's response has many top-level keys (discussions, videos, infobox, etc.)
    # We use only web.results — the classic ranked web results.
    web_block = data.get("web", {})
    raw_results = web_block.get("results", []) or []

    # Echo back the query as Brave saw it (after any spellcheck normalization)
    echoed_query = data.get("query", {}).get("original") or query.strip()

    items: list[SearchResultItem] = []
    for r in raw_results[: settings.search_result_count]:
        title = (r.get("title") or "").strip()[:200]
        url = (r.get("url") or "").strip()
        description_raw = r.get("description") or ""

        # Sanitize description: Brave wraps match terms in <strong>...</strong>
        # and may include HTML entities. Use sanitize_html which actually
        # parses tags out (sanitize_plain only collapses whitespace).
        sanitized = sanitize_html(description_raw, max_output_chars=MAX_DESCRIPTION_CHARS)

        if not (title and url):
            continue  # skip malformed results

        items.append(SearchResultItem(
            title=title,
            url=url,
            description=sanitized.text,
        ))

    return SearchResponse(query=echoed_query, results=items)
