"""Markdown chunker that respects section hierarchy.

Each section becomes one or more chunks. Sections that are too long get
split via the fixed-size chunker, but the section's heading path is
preserved on every resulting chunk.

The embedder sees the heading path prepended to the chunk text. This
makes embeddings location-aware - 'token generation' from 'Auth > OAuth'
embeds differently than the same text from 'API > Bearer Tokens'.
"""

from agent_api.ingest.chunkers.fixed import chunk_text
from agent_api.ingest.extractors.markdown import MarkdownSection
from agent_api.ingest.types import Chunk


# Hard cap on embeddable_text length. nomic-embed-text has an 8192-token
# context; we stay well below that in characters to leave room for
# multi-byte UTF-8 and tokenization overhead. If a section is bigger,
# we force-split via the fixed-size chunker.
MAX_EMBEDDABLE_CHARS = 4000


def _header_prefix(document_title: str, section_path: list[str]) -> str:
    """Build a 'Title > Section > Subsection.' prefix for embedding."""
    parts = [document_title] + section_path
    return " > ".join(parts) + "."


def chunk_markdown(
    sections: list[MarkdownSection],
    source_file: str,
    document_title: str,
    target_words: int = 350,
    overlap_words: int = 50,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    index = 0

    for section in sections:
        section_text = section.text.strip()
        if not section_text:
            continue

        prefix = _header_prefix(document_title, section.heading_path)
        words = section_text.split()

        # Split if the section is too many words OR if the resulting
        # embeddable text would be too long in characters.
        fits_word_budget = len(words) <= target_words
        fits_char_budget = len(prefix) + len(section_text) + 1 <= MAX_EMBEDDABLE_CHARS

        if fits_word_budget and fits_char_budget:
            chunks.append(
                Chunk(
                    text=section_text,
                    embeddable_text=f"{prefix} {section_text}",
                    source_file=source_file,
                    document_title=document_title,
                    section_path=list(section.heading_path),
                    chunk_index=index,
                    content_type="markdown",
                )
            )
            index += 1
        else:
            sub_chunks = chunk_text(
                text=section_text,
                source_file=source_file,
                document_title=document_title,
                content_type="markdown",
                base_chunk_index=index,
                target_words=target_words,
                overlap_words=overlap_words,
            )
            for c in sub_chunks:
                c.section_path = list(section.heading_path)
                c.embeddable_text = f"{prefix} {c.text}"
                # Defensive: if even fixed-size produced something too long
                # (shouldn't happen with target_words=350 but be safe), truncate.
                if len(c.embeddable_text) > MAX_EMBEDDABLE_CHARS:
                    c.embeddable_text = c.embeddable_text[:MAX_EMBEDDABLE_CHARS]
                chunks.append(c)
                index = c.chunk_index + 1

    return chunks
