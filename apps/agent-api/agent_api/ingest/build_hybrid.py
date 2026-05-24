"""Build a hybrid (dense + sparse) collection from an existing dense one.

Deterministic and source-independent: reads chunk text from the existing
collection's payloads, fits BM25 IDF over them, and writes a new collection
with NAMED dense + sparse vectors. The source collection is never modified, so
this is safe to run and verify before any swap.

Usage:
    python -m agent_api.ingest.build_hybrid --source phase-a --dest phase-a-hybrid
"""

from __future__ import annotations

import argparse
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from agent_api.ingest.sparse import BM25Encoder
from agent_api.settings import settings

DENSE_NAME = "dense"
SPARSE_NAME = "sparse"
_DENSE_DIM = 768


def _client() -> QdrantClient:
    host = settings.qdrant_host
    if host == "qdrant":
        host = "localhost"
    return QdrantClient(host=host, port=settings.qdrant_port)


def _scroll_all(c: QdrantClient, collection: str):
    """Yield all points (with vectors + payload) from a collection."""
    offset = None
    while True:
        pts, offset = c.scroll(
            collection_name=collection, limit=256,
            with_payload=True, with_vectors=True, offset=offset,
        )
        for p in pts:
            yield p
        if offset is None:
            break


def build(source: str, dest: str, idf_path: Path) -> dict:
    c = _client()

    # 1. Collect all points + chunk texts
    points = list(_scroll_all(c, source))
    texts = [(p.payload or {}).get("text", "") for p in points]
    print(f"read {len(points)} points from '{source}'")

    # 2. Fit BM25 IDF over the corpus, persist it (query time must reuse this)
    encoder = BM25Encoder.fit(texts)
    encoder.save(idf_path)
    print(f"fit BM25 IDF over {len(texts)} chunks -> {idf_path}")

    # 3. Recreate dest with named dense + sparse vectors
    existing = {col.name for col in c.get_collections().collections}
    if dest in existing:
        c.delete_collection(dest)
    c.create_collection(
        collection_name=dest,
        vectors_config={
            DENSE_NAME: qmodels.VectorParams(size=_DENSE_DIM, distance=qmodels.Distance.COSINE),
        },
        sparse_vectors_config={
            SPARSE_NAME: qmodels.SparseVectorParams(),
        },
    )
    print(f"created '{dest}' with named dense+sparse vectors")

    # 4. Migrate every point: keep dense vector + payload, add sparse from text
    new_points = []
    for p in points:
        dense_vec = p.vector  # unnamed flat list in the source
        if isinstance(dense_vec, dict):  # defensive: if source was named
            dense_vec = next(iter(dense_vec.values()))
        text = (p.payload or {}).get("text", "")
        sparse_vec = encoder.encode_document(text)
        new_points.append(
            qmodels.PointStruct(
                id=p.id,
                vector={DENSE_NAME: dense_vec, SPARSE_NAME: sparse_vec},
                payload=p.payload,
            )
        )

    BATCH = 128
    for i in range(0, len(new_points), BATCH):
        c.upsert(collection_name=dest, points=new_points[i:i + BATCH])
    print(f"upserted {len(new_points)} points into '{dest}'")

    # 5. Verify count
    dest_info = c.get_collection(dest)
    return {
        "source_points": len(points),
        "dest_points": dest_info.points_count,
        "idf_path": str(idf_path),
        "idf_terms": len(encoder._idf),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build hybrid collection from a dense one")
    ap.add_argument("--source", default="phase-a")
    ap.add_argument("--dest", default=settings.hybrid_collection)
    ap.add_argument("--idf", type=Path, default=None)
    args = ap.parse_args()
    idf_path = args.idf or (Path.cwd() / settings.bm25_idf_path)
    result = build(args.source, args.dest, idf_path)
    print()
    print("=== migration result ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    ok = result["source_points"] == result["dest_points"]
    print(f"\ncount match: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
