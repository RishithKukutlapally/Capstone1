# Two-Model Comparison (AC-10)

Generated: 2026-08-30T14:39:32

Both models answered the same golden set with identical retrieval, reranking
and prompts. Only the generator changed.

| Metric | `gemini-3.5-flash-lite` | `gemini-3.5-flash` |
|---|---|---|
| llm_context_precision_with_reference | 0.6856 | 0.6922 |
| context_recall | 0.9118 | 0.9265 |
| faithfulness | 1.0 | 0.8309 |
| answer_relevancy | 0.8542 | 0.8099 |
| samples_scored | 17 | 17 |
| pipeline_errors | 0 | 0 |
| questions_scored | 20 | 20 |
| retrieval_recall | 0.9655 | 0.8966 |
| clauses_found | 28/29 | 26/29 |
| abstention_accuracy | 1.0 | 1.0 |
| correct_abstentions | 3/3 | 3/3 |
| false_abstentions | 0 | 2 |
| citation_rate | 1.0 | 1.0 |
| answers_with_citation | 17/17 | 15/15 |
| mean_latency_seconds | 8.95 | 11.56 |

Selection rationale: see docs/model-selection.md