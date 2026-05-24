"""Generate downloadable files from chat content.

Ephemeral: files are produced in-request and streamed back, never stored.
The source content is the user's own (a chat response or requested content),
so there's no untrusted-injection concern — but the user-supplied filename
is sanitized to a safe basename to prevent path tricks in Content-Disposition.

Markdown export is a passthrough (the assistant already writes markdown).
PDF rendering parses the markdown with markdown-it-py and emits fpdf2 output,
handling headings, paragraphs, lists, code blocks, and inline formatting;
tables degrade to plain monospaced text.
"""

from __future__ import annotations

import re

MAX_CONTENT_CHARS = 100_000  # guard against giant blobs exhausting memory


def sanitize_filename(name: str | None, default_stem: str, extension: str) -> str:
    """Return a safe '<stem>.<extension>' filename.

    Strips directory separators and unsafe chars; falls back to default_stem.
    extension is the bare ext without a dot (e.g. 'md', 'pdf').
    """
    if not name:
        stem = default_stem
    else:
        # Drop any path, keep the basename, strip the extension if the user added one
        base = name.replace("\\", "/").split("/")[-1]
        base = re.sub(r"\.(md|markdown|pdf|txt)$", "", base, flags=re.IGNORECASE)
        # Keep only safe characters
        stem = re.sub(r"[^A-Za-z0-9 _.-]", "", base).strip().strip(".")
        stem = stem or default_stem
    stem = stem[:80]  # bound length
    return f"{stem}.{extension}"


def to_markdown(content: str) -> bytes:
    """Export content as a Markdown file (UTF-8 bytes). Passthrough."""
    return content.encode("utf-8")


import re as _re2
from fpdf import FPDF
from markdown_it import MarkdownIt


_INLINE_MARKERS = _re2.compile(r"(\*\*|__|\*|_|`)")

_TRANSLIT = {
    "\u2014": "-", "\u2013": "-",
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2026": "...",
    "\u2192": "->", "\u2190": "<-",
    "\u2022": "-",
    "\u00a0": " ",
}


def _latin1_safe(text: str) -> str:
    for k, v in _TRANSLIT.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def _strip_inline_markers(text: str) -> str:
    return _INLINE_MARKERS.sub("", text)


def _clean(text: str) -> str:
    return _latin1_safe(_strip_inline_markers(text))


class _DocPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(150)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(0)


def to_pdf(content: str, title: str = "Document") -> bytes:
    """Render markdown content to PDF bytes via a markdown-it token walk.

    Robustness notes:
    - X is reset to the left margin before every block, so a preceding list
      indent never shrinks a later block's available width (which caused
      'not enough horizontal space' on long code lines).
    - Code blocks use wrapmode='CHAR' so a long unbreakable token (e.g. a long
      command or URL with no spaces) wraps by character instead of raising.
    """
    pdf = _DocPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(left=18, top=15, right=18)

    md = MarkdownIt()
    tokens = md.parse(content or "")

    list_stack = []
    i = 0
    n = len(tokens)

    def reset_x():
        pdf.set_x(pdf.l_margin)

    def avail_width():
        return pdf.w - pdf.l_margin - pdf.r_margin

    def text_block(text, size, bold):
        reset_x()
        pdf.set_font("Helvetica", style="B" if bold else "", size=size)
        pdf.multi_cell(avail_width(), size * 0.55 + 2, _clean(text), wrapmode="CHAR")
        pdf.ln(1)

    while i < n:
        t = tokens[i]
        ttype = t.type

        if ttype == "heading_open":
            level = int(t.tag[1])
            size = {1: 18, 2: 15, 3: 13, 4: 12, 5: 11, 6: 11}.get(level, 12)
            inline = tokens[i + 1].content if i + 1 < n else ""
            pdf.ln(2)
            text_block(inline, size, True)
            i += 3
            continue

        if ttype == "paragraph_open":
            inline = tokens[i + 1].content if i + 1 < n else ""
            if list_stack:
                ctx = list_stack[-1]
                if ctx["type"] == "ol":
                    ctx["n"] += 1
                    marker = f"{ctx['n']}. "
                else:
                    marker = "- "
                indent = 6.0 * len(list_stack)
                pdf.set_font("Helvetica", size=11)
                pdf.set_x(pdf.l_margin + indent)
                pdf.multi_cell(avail_width() - indent, 7, _clean(marker + inline), wrapmode="CHAR")
                pdf.ln(0.5)
            else:
                text_block(inline, 11, False)
            i += 3
            continue

        if ttype == "bullet_list_open":
            list_stack.append({"type": "ul", "n": 0})
            i += 1
            continue
        if ttype == "ordered_list_open":
            list_stack.append({"type": "ol", "n": 0})
            i += 1
            continue
        if ttype in ("bullet_list_close", "ordered_list_close"):
            if list_stack:
                list_stack.pop()
            pdf.ln(1)
            i += 1
            continue

        if ttype == "fence":
            pdf.ln(1)
            pdf.set_font("Courier", size=9)
            pdf.set_fill_color(244, 244, 244)
            for line in t.content.rstrip("\n").split("\n"):
                reset_x()
                pdf.multi_cell(avail_width(), 5, _clean(line) or " ", fill=True, wrapmode="CHAR")
            pdf.ln(2)
            i += 1
            continue

        if ttype == "blockquote_open":
            j = i + 1
            quote_text = ""
            while j < n and tokens[j].type != "blockquote_close":
                if tokens[j].type == "inline":
                    quote_text += tokens[j].content + " "
                j += 1
            pdf.set_font("Helvetica", style="I", size=11)
            pdf.set_text_color(90)
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(avail_width() - 5, 6, _clean(quote_text.strip()), wrapmode="CHAR")
            pdf.set_text_color(0)
            pdf.ln(1)
            i = j + 1
            continue

        if ttype == "hr":
            pdf.ln(2)
            y = pdf.get_y()
            pdf.set_draw_color(200)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.set_draw_color(0)
            pdf.ln(3)
            i += 1
            continue

        if ttype == "table_open":
            j = i + 1
            pdf.set_font("Courier", size=9)
            while j < n and tokens[j].type != "table_close":
                if tokens[j].type == "inline" and tokens[j].content:
                    reset_x()
                    pdf.multi_cell(avail_width(), 5, _clean(tokens[j].content), wrapmode="CHAR")
                j += 1
            pdf.ln(2)
            i = j + 1
            continue

        i += 1

    out = pdf.output()
    return bytes(out)
