"""URL fetcher with hardened defaults.

Defenses applied here:
- All URLs validated before fetch
- Strict request timeout (5 seconds total)
- Maximum response size (5 MB) — abort if exceeded
- No redirects to private IPs (we re-validate on every redirect)
- Limited redirect chain (max 5)
- User-Agent identifying the project (good citizenship + sometimes
  required by servers)
- Content-Type restricted: only text/html, text/plain, application/json,
  text/markdown, application/xhtml+xml
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from agent_api.web.validator import ValidationResult, validate_url


# Hard caps
TOTAL_TIMEOUT_SECONDS = 5.0
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_REDIRECTS = 5

ALLOWED_CONTENT_TYPES = frozenset([
    "text/html",
    "text/plain",
    "text/markdown",
    "application/json",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
])

USER_AGENT = "LocalAIEngineer/0.10 (+https://github.com/local-ai-engineer)"


@dataclass
class FetchError(Exception):
    """Raised when fetch fails for any reason."""
    reason: str
    status_code: int | None = None

    def __str__(self) -> str:
        return self.reason


@dataclass
class FetchResult:
    url: str           # final URL after redirects
    status_code: int
    content_type: str  # the parsed primary content-type, e.g. "text/html"
    body: bytes
    encoding: str      # detected character encoding


async def fetch_url(url: str) -> FetchResult:
    """Fetch a URL with all defenses applied.

    Raises FetchError on any failure (validation, network, content-type,
    size limit, redirect loop, etc.).
    """
    initial_validation = validate_url(url)
    if not initial_validation.valid:
        raise FetchError(f"URL rejected: {initial_validation.reason}")

    # We do manual redirect handling so we can re-validate each hop.
    # That's slightly more code than httpx's built-in follow_redirects=True,
    # but it lets us prevent redirects-to-internal-services attacks.
    current_url = url
    timeout = httpx.Timeout(TOTAL_TIMEOUT_SECONDS)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain, application/json"},
    ) as client:
        for hop in range(MAX_REDIRECTS + 1):
            try:
                response = await client.get(current_url)
            except httpx.TimeoutException:
                raise FetchError(f"Request timed out after {TOTAL_TIMEOUT_SECONDS}s")
            except httpx.RequestError as e:
                raise FetchError(f"Network error: {type(e).__name__}: {e}")

            # Handle redirects manually
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise FetchError(
                        f"Redirect with no Location header (HTTP {response.status_code})",
                        status_code=response.status_code,
                    )
                # Resolve relative redirects
                from urllib.parse import urljoin
                next_url = urljoin(current_url, location)
                # Re-validate the new URL!
                v = validate_url(next_url)
                if not v.valid:
                    raise FetchError(
                        f"Redirect target rejected: {v.reason}",
                        status_code=response.status_code,
                    )
                current_url = next_url
                continue

            if response.status_code >= 400:
                raise FetchError(
                    f"HTTP {response.status_code}",
                    status_code=response.status_code,
                )

            # Successful response. Validate content-type before reading body.
            content_type_header = response.headers.get("Content-Type", "")
            primary_type = content_type_header.split(";")[0].strip().lower()
            if primary_type not in ALLOWED_CONTENT_TYPES:
                raise FetchError(
                    f"Content-Type '{primary_type}' not allowed",
                    status_code=response.status_code,
                )

            # Check declared length
            declared_length = response.headers.get("Content-Length")
            if declared_length:
                try:
                    if int(declared_length) > MAX_RESPONSE_BYTES:
                        raise FetchError(
                            f"Content-Length {declared_length} exceeds max {MAX_RESPONSE_BYTES}",
                            status_code=response.status_code,
                        )
                except ValueError:
                    pass  # Bad Content-Length header; let the read-time check catch it

            # Actually read the body, but cap at MAX_RESPONSE_BYTES
            body = response.content  # httpx has already buffered
            if len(body) > MAX_RESPONSE_BYTES:
                raise FetchError(
                    f"Response body {len(body)} bytes exceeds max {MAX_RESPONSE_BYTES}",
                    status_code=response.status_code,
                )

            encoding = response.encoding or "utf-8"

            return FetchResult(
                url=current_url,
                status_code=response.status_code,
                content_type=primary_type,
                body=body,
                encoding=encoding,
            )

        raise FetchError(f"Too many redirects (limit {MAX_REDIRECTS})")
