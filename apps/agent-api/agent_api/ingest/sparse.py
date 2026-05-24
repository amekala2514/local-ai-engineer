"""BM25 sparse-vector encoder for hybrid retrieval.

Produces Qdrant SparseVector (integer indices + float weights) from text, used
at BOTH index time and query time. The two MUST use the same tokenizer and the
same corpus IDF, or fusion scores are meaningless — so IDF is computed once
from the corpus and persisted, and the tokenizer is deterministic.

Indexing weight (per document term): BM25 TF saturation * IDF.
Query weight (per query term): IDF (standard BM25 query-side weighting).

Token -> index: a stable 32-bit hash, so no vocabulary map needs persisting;
only IDF (keyed by the same hash) is persisted.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from qdrant_client.http import models as qmodels

# BM25 parameters (standard defaults)
_K1 = 1.5
_B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_MIN_TOKEN_LEN = 2
_HASH_MOD = 2_147_483_647  # keep indices in int32 range


def tokenize(text: str) -> list[str]:
    """Deterministic tokenizer used identically at index and query time."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= _MIN_TOKEN_LEN]


def _token_index(token: str) -> int:
    """Stable hash of a token to a non-negative int32 index.

    Uses a simple deterministic hash (not Python's salted hash()) so indices
    are identical across processes/runs.
    """
    h = 2166136261
    for ch in token.encode("utf-8"):
        h = (h ^ ch) * 16777619 & 0xFFFFFFFF
    return h % _HASH_MOD


class BM25Encoder:
    """Holds corpus IDF and average doc length; encodes docs and queries."""

    def __init__(self, idf: dict[int, float], avg_doc_len: float) -> None:
        self._idf = idf
        self._avg_doc_len = avg_doc_len if avg_doc_len > 0 else 1.0

    # ---- construction ----

    @classmethod
    def fit(cls, corpus: list[str]) -> "BM25Encoder":
        """Compute IDF + average doc length from the corpus chunk texts."""
        n_docs = len(corpus)
        df: dict[int, int] = {}
        total_len = 0
        for text in corpus:
            toks = tokenize(text)
            total_len += len(toks)
            for idx in {_token_index(t) for t in toks}:  # df = doc freq, unique per doc
                df[idx] = df.get(idx, 0) + 1
        # BM25 IDF with the standard +0.5 smoothing
        idf = {
            idx: math.log(1 + (n_docs - d + 0.5) / (d + 0.5))
            for idx, d in df.items()
        }
        avg = total_len / n_docs if n_docs else 1.0
        return cls(idf=idf, avg_doc_len=avg)

    # ---- persistence (so query time matches index time) ----

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {"avg_doc_len": self._avg_doc_len,
                 "idf": {str(k): v for k, v in self._idf.items()}},
                f,
            )

    @classmethod
    def load(cls, path: Path) -> "BM25Encoder":
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        idf = {int(k): v for k, v in data["idf"].items()}
        return cls(idf=idf, avg_doc_len=data["avg_doc_len"])

    # ---- encoding ----

    def encode_document(self, text: str) -> qmodels.SparseVector:
        """BM25 document weighting: TF saturation * IDF, per term."""
        toks = tokenize(text)
        dl = len(toks)
        tf: dict[int, int] = {}
        for t in toks:
            idx = _token_index(t)
            tf[idx] = tf.get(idx, 0) + 1
        indices: list[int] = []
        values: list[float] = []
        for idx, f in tf.items():
            idf = self._idf.get(idx)
            if idf is None:
                continue  # term unseen in corpus -> no signal
            denom = f + _K1 * (1 - _B + _B * dl / self._avg_doc_len)
            weight = idf * (f * (_K1 + 1)) / denom
            if weight > 0:
                indices.append(idx)
                values.append(weight)
        return qmodels.SparseVector(indices=indices, values=values)

    def encode_query(self, text: str) -> qmodels.SparseVector:
        """Query weighting: IDF per unique term (standard BM25 query side)."""
        indices: list[int] = []
        values: list[float] = []
        for t in set(tokenize(text)):
            idx = _token_index(t)
            idf = self._idf.get(idx)
            if idf is not None and idf > 0:
                indices.append(idx)
                values.append(idf)
        return qmodels.SparseVector(indices=indices, values=values)
