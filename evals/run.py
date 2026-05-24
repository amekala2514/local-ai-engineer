"""Retrieval eval harness.

Usage:
    .venv/bin/python -m evals.run                  # use the retriever (with rerank if enabled)
    .venv/bin/python -m evals.run --no-rerank      # force vector-only

Writes a timestamped markdown report to evals/runs/.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "apps" / "agent-api"))

from agent_api.ingest.embedder import close as close_embedder  # noqa: E402
from agent_api.ingest.qdrant_store import SearchResult, search  # noqa: E402
from agent_api.rag.retriever import retrieve_for_query  # noqa: E402
from agent_api.rag.query_transform import rewrite_query, generate_hyde_doc  # noqa: E402
from agent_api.models.ollama import OllamaClient  # noqa: E402
from agent_api.settings import settings  # noqa: E402


VERDICT_HIT = "hit"
VERDICT_NEAR = "near-miss"
VERDICT_MISS = "miss"


@dataclass
class EvalQuestion:
    id: str
    question: str
    expected_source: str
    expected_keywords: list[str]
    category: str


@dataclass
class EvalResult:
    question: EvalQuestion
    results: list[SearchResult]
    verdict: str
    matched_source_rank: int | None
    matched_keywords: list[str]


def load_questions(path: Path) -> tuple[str, list[EvalQuestion]]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    collection = data.get("collection", "phase-a")
    questions = [
        EvalQuestion(
            id=q["id"],
            question=q["question"],
            expected_source=q["expected_source"],
            expected_keywords=q.get("expected_keywords", []),
            category=q.get("category", "uncategorized"),
        )
        for q in data["questions"]
    ]
    return collection, questions


def score_result(q: EvalQuestion, results: list[SearchResult]) -> EvalResult:
    matched_rank: int | None = None
    for i, r in enumerate(results, start=1):
        src_name = Path(r.source_file).name
        if q.expected_source.lower() in src_name.lower():
            matched_rank = i
            break

    haystack = " ".join(r.text.lower() for r in results)
    matched_keywords = [
        kw for kw in q.expected_keywords if kw.lower() in haystack
    ]
    keyword_threshold = max(1, len(q.expected_keywords) // 2)
    keywords_pass = len(matched_keywords) >= keyword_threshold

    if matched_rank is not None and keywords_pass:
        verdict = VERDICT_HIT
    elif matched_rank is not None:
        verdict = VERDICT_NEAR
    else:
        verdict = VERDICT_MISS

    return EvalResult(
        question=q,
        results=results,
        verdict=verdict,
        matched_source_rank=matched_rank,
        matched_keywords=matched_keywords,
    )


def render_report(
    collection: str,
    eval_results: list[EvalResult],
    top_k: int,
    rerank: bool,
    started_at: datetime.datetime,
    finished_at: datetime.datetime,
) -> str:
    total = len(eval_results)
    hits = sum(1 for r in eval_results if r.verdict == VERDICT_HIT)
    near = sum(1 for r in eval_results if r.verdict == VERDICT_NEAR)
    miss = sum(1 for r in eval_results if r.verdict == VERDICT_MISS)

    by_cat: dict[str, dict[str, int]] = {}
    for r in eval_results:
        cat = r.question.category
        by_cat.setdefault(cat, {VERDICT_HIT: 0, VERDICT_NEAR: 0, VERDICT_MISS: 0})
        by_cat[cat][r.verdict] += 1

    lines: list[str] = []
    rerank_label = "rerank=on" if rerank else "rerank=off"
    lines.append(f"# Eval run — {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")
    lines.append(f"**Collection:** `{collection}`  ")
    lines.append(f"**Top-K:** {top_k}  ")
    lines.append(f"**Reranker:** `{rerank_label}`  ")
    duration = (finished_at - started_at).total_seconds()
    lines.append(f"**Duration:** {duration:.1f}s  ")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total questions: **{total}**")
    lines.append(f"- Hits: **{hits}** ({100 * hits / total:.0f}%)")
    lines.append(f"- Near-misses: **{near}** ({100 * near / total:.0f}%)")
    lines.append(f"- Misses: **{miss}** ({100 * miss / total:.0f}%)")
    lines.append("")
    lines.append("## By category")
    lines.append("")
    lines.append("| Category | Hit | Near | Miss |")
    lines.append("|---|---|---|---|")
    for cat in sorted(by_cat):
        counts = by_cat[cat]
        lines.append(
            f"| {cat} | {counts[VERDICT_HIT]} | {counts[VERDICT_NEAR]} | {counts[VERDICT_MISS]} |"
        )
    lines.append("")
    lines.append("## Per-question results")
    lines.append("")
    for r in eval_results:
        marker = {VERDICT_HIT: "✅", VERDICT_NEAR: "⚠️", VERDICT_MISS: "❌"}[r.verdict]
        lines.append(f"### {marker} {r.question.id} — {r.verdict}")
        lines.append("")
        lines.append(f"**Question:** {r.question.question}")
        lines.append("")
        lines.append(f"**Expected source:** `{r.question.expected_source}`  ")
        if r.matched_source_rank:
            lines.append(f"**Found at rank:** {r.matched_source_rank}  ")
        else:
            lines.append(f"**Found at rank:** not in top-{top_k}  ")
        kw_hit = len(r.matched_keywords)
        kw_total = len(r.question.expected_keywords)
        lines.append(f"**Keywords matched:** {kw_hit}/{kw_total} ({', '.join(r.matched_keywords) or 'none'})")
        lines.append("")
        lines.append("Top results:")
        for i, sr in enumerate(r.results, start=1):
            loc = ""
            if sr.section_path:
                loc = " > ".join(sr.section_path)
            elif sr.page_number is not None:
                loc = f"page {sr.page_number}"
            src_name = Path(sr.source_file).name
            line = f"  {i}. `{src_name}` — score `{sr.score:.3f}`"
            if loc:
                line += f" ({loc})"
            lines.append(line)
        lines.append("")
    return "\n".join(lines)


async def _transform(query: str, mode: str, client) -> str:
    if mode == "rewrite":
        return await rewrite_query(query, client)
    if mode == "hyde":
        return await generate_hyde_doc(query, client)
    return query


async def run_one(q: EvalQuestion, collection: str, top_k: int, rerank: bool,
                  transform: str = "none", client=None) -> EvalResult:
    query = await _transform(q.question, transform, client)
    if rerank:
        ctx = await retrieve_for_query(
            query=query,
            collection_id=collection,
            top_k=top_k,
            reason="eval",
            rerank=True,
        )
        results = ctx.chunks
    else:
        results = search(collection, query, top_k=top_k)
    return score_result(q, results)


async def main_async(args) -> int:
    started_at = datetime.datetime.now(datetime.timezone.utc)
    print(f"Loading questions from {args.questions}…")
    collection, questions = load_questions(args.questions)
    if args.collection:
        collection = args.collection

    rerank_label = "with rerank" if args.rerank else "without rerank"
    print(f"Running {len(questions)} questions {rerank_label} against '{collection}' (top-K={args.top_k})…")

    _client = None
    if args.transform != "none":
        host = settings.ollama_host
        if "host.docker.internal" in host:
            host = host.replace("host.docker.internal", "localhost")
        _client = OllamaClient(host=host)
        print(f"Query transform: {args.transform} (model {settings.query_transform_model})")
    eval_results: list[EvalResult] = []
    try:
        for q in questions:
            er = await run_one(q, collection, args.top_k, args.rerank,
                               transform=args.transform, client=_client)
            eval_results.append(er)
            marker = {VERDICT_HIT: "✓", VERDICT_NEAR: "~", VERDICT_MISS: "✗"}[er.verdict]
            print(f"  [{marker}] {q.id}: {er.verdict}")
    finally:
        close_embedder()

    finished_at = datetime.datetime.now(datetime.timezone.utc)
    report = render_report(collection, eval_results, args.top_k, args.rerank, started_at, finished_at)

    args.out.mkdir(parents=True, exist_ok=True)
    stamp = started_at.strftime("%Y-%m-%dT%H-%M-%SZ")
    suffix = "rerank" if args.rerank else "vector"
    if args.transform != "none":
        suffix = f"{suffix}-{args.transform}"
    out_path = args.out / f"{stamp}-{suffix}.md"
    out_path.write_text(report, encoding="utf-8")

    total = len(eval_results)
    hits = sum(1 for r in eval_results if r.verdict == VERDICT_HIT)
    near = sum(1 for r in eval_results if r.verdict == VERDICT_NEAR)
    miss = sum(1 for r in eval_results if r.verdict == VERDICT_MISS)
    print()
    print(f"Hit: {hits}/{total} ({100 * hits / total:.0f}%)")
    print(f"Near-miss: {near}/{total}")
    print(f"Miss: {miss}/{total}")
    print()
    print(f"Report written to: {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation")
    parser.add_argument("--questions", type=Path, default=_ROOT / "evals" / "questions.yaml")
    parser.add_argument("--out", type=Path, default=_ROOT / "evals" / "runs")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--no-rerank", dest="rerank", action="store_false", default=True,
                        help="Use plain vector search instead of reranking")
    parser.add_argument("--transform", choices=["none", "rewrite", "hyde"], default="none",
                        help="Apply a query transform before retrieval")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
