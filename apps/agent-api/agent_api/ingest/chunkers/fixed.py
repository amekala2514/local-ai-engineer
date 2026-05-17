"""Fixed-size chunker with overlap.

Splits text into chunks of approximately N tokens (we use word count as a
cheap approximation since exact tokenization depends on the model).
Adjacent chunks overlap so information at boundaries isn't lost.
"""

from agent_api.ingest.types import Chunk


def chunk_text(
    text: str,
    source_file: str,
    document_title: str,
    content_type: str,
    base_chunk_index: int = 0,
    page_number: int | None = None,
    target_words: int = 350,
    overlap_words: int = 50,
) -> list[Chunk]:
    """Split a chunk of text into fixed-size pieces.

    Returns a list of Chunks. `base_chunk_index` lets the caller stitch
    multiple invocations into a single document's chunk index space.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    step = max(1, target_words - overlap_words)
    index = base_chunk_index

    for start in range(0, len(words), step):
        end = min(start + target_words, len(words))
        piece = " ".join(words[start:end])
        if not piece.strip():
            continue

        # Embeddable text prepends the document title for context
        embeddable = f"{document_title}. {piece}"

        chunks.append(
            Chunk(
                text=piece,
                embeddable_text=embeddable,
                source_file=source_file,
                document_title=document_title,
                section_path=[],
                chunk_index=index,
                content_type=content_type,
                page_number=page_number,
            )
        )
        index += 1

        if end == len(words):
            break

    return chunks
