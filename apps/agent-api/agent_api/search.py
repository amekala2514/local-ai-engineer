"""CLI: python -m agent_api.search "<query>" --collection <name>

Prints the top-K retrieved chunks. Used to validate retrieval quality
before wiring RAG into the chat (Day 11).

Use --brief for a one-line-per-result summary (good for sweeps).
"""

import argparse
import sys
from pathlib import Path

from agent_api.ingest.embedder import close as close_embedder
from agent_api.ingest.qdrant_store import search


def _format_location(r) -> str:
    """Return a short '(...)' location string for a result, or empty."""
    if r.section_path:
        return f"({' > '.join(r.section_path)})"
    if r.page_number is not None:
        return f"(page {r.page_number})"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Search a Qdrant collection.")
    parser.add_argument("query", help="The question or query text")
    parser.add_argument(
        "--collection",
        required=True,
        help="Name of the Qdrant collection to search",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="One-line-per-result output for fast sweeps",
    )
    args = parser.parse_args()

    try:
        results = search(args.collection, args.query, top_k=args.top_k)
    finally:
        close_embedder()

    if args.brief:
        # Compact format: one line per result
        print(f'Query: "{args.query}"')
        if not results:
            print("  (no results)")
        else:
            for i, r in enumerate(results, start=1):
                src_name = Path(r.source_file).name
                loc = _format_location(r)
                line = f"  [{i}] score={r.score:.3f}  {src_name}"
                if loc:
                    line += f"  {loc}"
                print(line)
        return 0 if results else 1

    # Verbose format (default): full chunk text
    print(f"Query: {args.query}")
    print(f"Collection: {args.collection}")
    print("-" * 80)

    if not results:
        print("No results.")
        return 1

    for i, r in enumerate(results, start=1):
        src_name = Path(r.source_file).name
        loc = _format_location(r)
        header = f"[{i}] score={r.score:.3f}  {src_name}"
        if loc:
            header += f"  {loc}"
        print(header)
        print()
        snippet = r.text.strip()
        if len(snippet) > 600:
            snippet = snippet[:600].rstrip() + "..."
        print(snippet)
        print()
        print("-" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
