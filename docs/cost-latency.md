# Cost and Latency Note

Satisfies NFR-07, which asks for a **concept-level** note on the approximate
cost and latency of a representative query. No benchmarking or performance
governance is required or attempted here. Figures are order-of-magnitude
estimates from observed runs on a CPU-only Windows laptop, not a controlled
benchmark.

---

## Representative query

> *"What warning is required for a product with a button cell battery?"*

Typical of the workload: a single-part question, answerable from one clause,
with a handful of related clauses retrieved alongside it.

## Where the time goes

| Step | Runs on | Approx. time | Notes |
|---|---|---|---|
| 1. Query transformation | Gemini API | ~5–10 s | One LLM call. Skipped for questions under 60 characters. |
| 2a. BM25 search | Local CPU | < 50 ms | 300 chunks held in memory |
| 2b. Vector search | Local CPU | ~40 ms | One embedding of the query, then an HNSW lookup over 300 vectors |
| 3. RRF fusion | Local CPU | < 5 ms | Pure arithmetic over ~40 candidates |
| 4. Cross-encoder rerank | Local CPU | ~200–400 ms | 12 (query, passage) pairs through a 22M-parameter model |
| 5. Generation | Gemini API | ~15–20 s | One LLM call with structured output |
| 6. Guardrail checks | Local CPU | < 5 ms | Set membership and threshold comparisons |
| **Total** | | **~25 s** | Measured end to end |

**The two API calls are ~99% of the wall-clock time.** Everything the project
actually engineers — hybrid search, fusion, reranking, guardrails — costs under
half a second combined.

An **abstention on an out-of-corpus question returns in ~0.2 s**, because
reranking drops everything below threshold and the pipeline never makes the
generation call at all. Refusing is roughly a hundred times cheaper than
answering, which is a pleasant property for a system designed to refuse often.

## Cost per query

Two Gemini calls per answered question.

| | Approx. tokens |
|---|---|
| Query transformation — input | ~400 (system prompt + question) |
| Query transformation — output | ~100 |
| Generation — input | ~2,000 (system prompt + 5 retrieved clauses + question) |
| Generation — output | ~400 (structured answer with citations) |
| **Total per query** | **~2,400 in / ~500 out** |

At Gemini Flash-class pricing this is a **fraction of a US cent per query** —
low four-figure token counts either side. Even at ten thousand queries a month
the model spend stays in the low tens of dollars.

**Embeddings and reranking cost nothing per query.** Both models run locally, so
they are a fixed one-off download (~130 MB and ~90 MB) and then free forever.
This is a meaningful part of the architecture's economics: a hosted embedding
API would add a per-query charge to every retrieval, including the ones that end
in abstention.

## Ingestion cost

Ingesting the full 30-document corpus embeds 300 chunks locally in well under a
minute on CPU, and costs **nothing** — no API is involved. Re-ingestion is
idempotent, so routine re-runs are cheap.

## Evaluation cost

The heaviest operation in the project.

| Operation | Gemini calls |
|---|---|
| Answer 24 golden questions | ~48 (two per question) |
| RAGAS judging, 4 metrics × ~21 scorable questions | ~84+ |
| Two-model comparison (runs the golden set again per model) | ~96 |

A full `catalog-rag all` therefore makes a few hundred API calls and takes
roughly 30–45 minutes on a billing-enabled key. On a free-tier key it takes
considerably longer, because the ~10 requests-per-minute limit triggers the
retry backoff — raise `eval.request_delay_seconds` to 2–4 in that case.

## Obvious levers, if latency ever mattered

Not implemented, because NFR-07 is concept-level only:

1. **Skip query transformation on short questions.** Already done — questions
   under `query_transform.min_chars_for_decomposition` bypass the call entirely,
   removing ~40% of the latency.
2. **Cache answers for repeated questions.** Catalog operations questions repeat
   heavily; a simple cache keyed on the normalised question would eliminate both
   API calls on a hit.
3. **Run the two arms concurrently.** They are independent, and both are local,
   so the saving is small — tens of milliseconds against a 25-second total.
4. **Stream the generation.** Does not reduce total time, but the user starts
   reading several seconds sooner.
5. **Use a flash-lite class model.** Roughly halves generation latency and cost;
   the quality trade-off is measured in `reports/model_comparison.md`.

Levers 1 and 2 are the only ones worth having. The rest optimise the 1% of the
budget that is not spent waiting on the provider.
