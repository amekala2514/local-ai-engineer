"""CLI: python -m agent_api.ingest <path> --collection <name>

Examples:
  python -m agent_api.ingest ~/Downloads/cncf-operator-whitepaper.pdf --collection phase-a
  python -m agent_api.ingest ~/Downloads/kubernetes-website/content/en/docs/concepts/workloads/pods --collection phase-a
"""

import argparse
import sys
from pathlib import Path

from agent_api.ingest.embedder import close as close_embedder
from agent_api.ingest.pipeline import ingest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest documents into a Qdrant collection.")
    parser.add_argument("path", type=Path, help="File or directory to ingest")
    parser.add_argument(
        "--collection",
        required=True,
        help="Name of the Qdrant collection to upsert into",
    )
    args = parser.parse_args()

    path = args.path.expanduser().resolve()
    print(f"Ingesting {path} into collection '{args.collection}'...")

    try:
        results = ingest_path(path, args.collection)
    finally:
        close_embedder()

    total_chunks = 0
    total_stored = 0
    failed: list[str] = []
    for r in results:
        status = "OK" if not r.errors else "FAIL"
        print(f"  [{status}] {Path(r.source_file).name}: {r.chunks_stored} chunks")
        if r.errors:
            for e in r.errors:
                print(f"         {e}")
                failed.append(f"{r.source_file}: {e}")
        total_chunks += r.chunks_created
        total_stored += r.chunks_stored

    print()
    print(f"Total files processed: {len(results)}")
    print(f"Total chunks created: {total_chunks}")
    print(f"Total chunks stored:  {total_stored}")
    if failed:
        print(f"Failures: {len(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
