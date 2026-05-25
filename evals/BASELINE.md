# Retrieval Eval Baseline (Day 27)

Canonical baseline for the retrieval pipeline, recorded 2026-05-25. Future
retrieval changes are measured against these numbers. Re-run any config with
`python -m evals.run --no-rerank [--transform hyde] [--hybrid]`.

## Question set
22 questions (`evals/questions.yaml`). q01-q18 are the original set; q19-q22
are hard questions added by measurement (each confirmed hard for plain dense
retrieval — expected source at rank 4+ or absent — with a topic-probe
confirming the answer genuinely lives in the expected source).

## Scoring (Day 27 revision)
Verdict is now SOURCE-based; keyword coverage is informational, not a gate.
- HIT  = expected source retrieved within the top 3
- NEAR = expected source retrieved but at rank 4-5 (found but buried)
- MISS = expected source not retrieved at all
- MRR  = mean reciprocal rank over the expected source (rank quality)
- Keyword coverage = avg expected-keywords found in retrieved text (a signal
  about the question's keyword list, NOT a pass/fail; previously this gated
  the verdict and produced false near-misses on q07/q09 — correct doc at
  rank 1 but hand-authored keywords absent from the chunk).

## Results (phase-a, top_k=5)

| Config              | Hit        | Near | Miss | MRR   | Transform | Retrieval |
|---------------------|------------|------|------|-------|-----------|-----------|
| Dense baseline      | 17/22 (77%)| 2    | 3    | 0.763 | 0 ms      | ~31 ms    |
| HyDE alone          | 19/22 (86%)| 2    | 1    | 0.859 | ~1140 ms  | ~33 ms    |
| Hybrid alone        | 19/22 (86%)| 1    | 2    | 0.822 | 0 ms      | ~24 ms    |
| **HyDE + hybrid***  | **22/22**  | **0**| **0**| **0.977** | ~1140 ms | ~35 ms |

*Shipped config (`hyde_enabled=True`, `hybrid_enabled=True`).

## Reading the baseline
- The shipped config retrieves the correct source for all 22 questions, nearly
  all at rank 1 (MRR 0.977). It is best on every quality axis.
- HyDE and hybrid each reach 19/22 but fix DIFFERENT questions (HyDE: vocab
  mismatch; hybrid/BM25: distinctive keywords like "GPU"). Combining them
  reaches 22/22 — the aggregate hit count hid this; MRR and per-question
  reading reveal it.
- Cost: HyDE's transform adds ~1.1s (a separate LLM call); hybrid retrieval is
  nearly free (~5ms over dense). The quality gain (77%->100% hit, 0.76->0.98
  MRR) justifies HyDE's latency for this corpus.
  (Note: an O2 trace measured HyDE at ~3.1s on a cold/long query; the eval's
  ~1.1s avg reflects warm-model, shorter-prompt conditions. HyDE latency is
  query- and warmth-dependent; treat ~1-3s as the range.)

## Known limitations / deferred
- SATURATION: at 100% hit / 0.977 MRR, this eval can no longer discriminate
  further retrieval improvements. Measuring future retrieval work requires
  adding harder questions (as q19-q22 were added when the original 18
  saturated).
- RETRIEVAL != ANSWER QUALITY: the eval scores source retrieval, not whether
  the model uses the retrieved chunk well. q22 is the standing example — its
  source now retrieves at rank 1, but the model still hedged on the answer
  because the chunk doesn't cleanly state the GPU-request mechanism. A proper
  answer-quality eval (grading generated answers, not just retrieval) is
  deferred — it needs answer-grading infrastructure and is a project of its
  own (candidate for Phase C).
