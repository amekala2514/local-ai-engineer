"""Prompt assembly for RAG-grounded answers.

Takes a RetrievalContext and the user's message, returns a system prompt
that frames the chunks for the model with citation instructions.

The framing matters. The model needs to:
  1. Know what the chunks are (excerpts from user's documents)
  2. Know how to use them (cite, don't guess)
  3. Have permission to say 'I don't know' rather than hallucinate
"""

from pathlib import Path

from agent_api.rag.retriever import RetrievalContext


def _format_chunk_location(chunk) -> str:
    """Return a 'filename, section/page' string for citation."""
    src_name = Path(chunk.source_file).name
    if chunk.section_path:
        loc = " > ".join(chunk.section_path)
        return f"{src_name}, section \"{loc}\""
    if chunk.page_number is not None:
        return f"{src_name}, page {chunk.page_number}"
    return src_name


def build_rag_system_prompt(context: RetrievalContext) -> str:
    """Build the system prompt for a RAG-grounded reply."""
    if not context.chunks:
        return (
            "You are an engineering assistant. The user has attached a knowledge "
            "collection, but no relevant excerpts were found for their question. "
            "Tell the user clearly that the attached documents do not appear to "
            "cover this question. Do not guess or fall back to general knowledge "
            "as if it were from the documents. If you want to answer from your "
            "general knowledge anyway, say so explicitly."
        )

    excerpts = []
    for i, chunk in enumerate(context.chunks, start=1):
        location = _format_chunk_location(chunk)
        excerpts.append(
            f"[{i}] From {location}:\n{chunk.text.strip()}"
        )
    excerpts_block = "\n\n".join(excerpts)

    return (
        "You are an engineering assistant. The user has attached a knowledge "
        "collection of documents. Below are excerpts retrieved as relevant to "
        "the user's question.\n\n"
        "When answering:\n"
        "- Ground your answer in the excerpts. Cite the source for each substantive claim.\n"
        "- If the excerpts don't contain enough information to answer fully, say so clearly.\n"
        "- Do not invent details that aren't in the excerpts. If you fall back on general "
        "knowledge for context, say so explicitly.\n"
        "- Cite sources inline using the bracket numbers, like [1] or [2].\n\n"
        "EXCERPTS:\n"
        "---\n"
        f"{excerpts_block}\n"
        "---"
    )
