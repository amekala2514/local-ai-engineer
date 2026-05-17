"""Markdown text extraction with section structure.

Returns the document broken into sections, each with its full heading path.
We use heading hierarchy as the structural unit; later chunking respects this.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MarkdownSection:
    """One section of a markdown document, identified by heading path."""

    heading_path: list[str]   # e.g., ["Pods", "Init Containers", "Lifecycle"]
    text: str                 # Body text under the deepest heading


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _clean_frontmatter(lines: list[str]) -> list[str]:
    """Strip Hugo/Jekyll-style YAML frontmatter if present."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1:]
    return lines


def _strip_hugo_shortcodes(text: str) -> str:
    """Remove {{< ... >}} and {{% ... %}} blocks that Kubernetes docs use."""
    text = re.sub(r"\{\{<.*?>\}\}", "", text, flags=re.DOTALL)
    text = re.sub(r"\{\{%.*?%\}\}", "", text, flags=re.DOTALL)
    return text


def extract_markdown(path: Path) -> tuple[str, list[MarkdownSection]]:
    """Read a markdown file and return (document_title, list of sections).

    The document title is taken from the first H1, or the filename.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = _strip_hugo_shortcodes(raw)
    lines = raw.splitlines()
    lines = _clean_frontmatter(lines)

    sections: list[MarkdownSection] = []
    current_path: list[str] = []
    current_levels: list[int] = []  # heading depth (1-6) at each level
    buffer: list[str] = []
    doc_title: str | None = None

    def flush() -> None:
        if buffer:
            text = "\n".join(buffer).strip()
            if text:
                sections.append(
                    MarkdownSection(
                        heading_path=list(current_path),
                        text=text,
                    )
                )
            buffer.clear()

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            depth = len(m.group(1))
            heading = m.group(2).strip()

            # Save the buffered text under the previous heading
            flush()

            # Pop deeper or equal headings from the stack
            while current_levels and current_levels[-1] >= depth:
                current_levels.pop()
                current_path.pop()

            current_levels.append(depth)
            current_path.append(heading)

            if doc_title is None and depth == 1:
                doc_title = heading
        else:
            buffer.append(line)

    flush()

    if doc_title is None:
        doc_title = path.stem

    return doc_title, sections
