"""Convert fetched HTML/text to clean plain text for LLM consumption.

The output is intended to be shown to the LLM as untrusted reference
content. The framing of "this is untrusted" is the responsibility of the
prompt builder; this module just produces clean text.

Defenses applied:
- Strip script, style, iframe, object, embed tags entirely
- Strip comments, which often contain HTML-injected instructions
- Collapse whitespace
- Cap output length (10000 chars by default; rough estimate ~2500 tokens)
- Preserve basic structure (paragraphs, lists, headings) for readability
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment


DEFAULT_MAX_OUTPUT_CHARS = 10000

# Tags whose content we want to drop entirely
DROP_TAGS = ["script", "style", "iframe", "object", "embed", "noscript", "svg", "canvas"]


@dataclass
class SanitizeResult:
    text: str
    title: str | None
    truncated: bool


def sanitize_html(html: str, max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS) -> SanitizeResult:
    """Strip HTML to clean plain text, capped at max_output_chars."""
    # Prefer lxml if available (faster), fall back to html.parser
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Title for metadata
    title = None
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)[:200]

    # Drop unwanted tags and their content
    for tag_name in DROP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Drop HTML comments (often used for hidden instructions)
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # Extract text. The separator="\n" gives us paragraph breaks.
    text = soup.get_text(separator="\n", strip=True)

    # Collapse runs of whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    truncated = len(text) > max_output_chars
    if truncated:
        text = text[:max_output_chars] + "\n\n[...content truncated...]"

    return SanitizeResult(text=text, title=title, truncated=truncated)


def sanitize_plain(text: str, max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS) -> SanitizeResult:
    """For text/plain or text/markdown responses, basic cleanup only."""
    # Normalize line endings and collapse runs
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    truncated = len(cleaned) > max_output_chars
    if truncated:
        cleaned = cleaned[:max_output_chars] + "\n\n[...content truncated...]"

    return SanitizeResult(text=cleaned, title=None, truncated=truncated)


def sanitize_response(content_type: str, body: bytes, encoding: str = "utf-8") -> SanitizeResult:
    """Dispatch based on content-type. Used by the fetch_url endpoint."""
    try:
        text = body.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        text = body.decode("utf-8", errors="replace")

    if content_type in ("text/html", "application/xhtml+xml"):
        return sanitize_html(text)
    return sanitize_plain(text)
