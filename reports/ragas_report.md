# RAGAS Evaluation Report

Generated: 2026-08-30T15:18:15  
Generator: `gemini-3.5-flash-lite` · Judge: `gemini-3.5-flash-lite` · Embeddings: `BAAI/bge-small-en-v1.5` · Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2`

## RAGAS metrics (AC-09)

| Metric | Score |
|---|---|
| llm_context_precision_with_reference | 0.6435 |
| context_recall | 0.9118 |
| faithfulness | 1.0 |
| answer_relevancy | 0.8573 |
| samples_scored | 17 |

Abstention questions are excluded: a correct abstention has no retrieved
context by design. They are measured below.

## Deterministic metrics

| Metric | Value |
|---|---|
| pipeline_errors | 0 |
| questions_scored | 20 |
| retrieval_recall | 0.9655 |
| clauses_found | 28/29 |
| abstention_accuracy | 1.0 |
| correct_abstentions | 3/3 |
| false_abstentions | 0 |
| citation_rate | 1.0 |
| answers_with_citation | 17/17 |
| mean_latency_seconds | 8.95 |

## Per-question results

A dash means the question was excluded from RAGAS scoring: abstention
questions have no retrieved context to score against.

| ID | Type | Status | Expected found | Citations | Context precision | Context recall | Faithfulness | Answer relevancy |
|---|---|---|---|---|---|---|---|---|
| G01 | single_clause_lookup | answered | 1/1 | 1 | 1.0 | 1.0 | 1.0 | 0.9356 |
| G03 | single_clause_lookup | answered | 1/1 | 1 | 1.0 | 0.5 | 1.0 | 0.9114 |
| G07 | exact_term_lookup | answered | 1/1 | 1 | 1.0 | 1.0 | 1.0 | 0.9083 |
| G08 | exact_term_lookup | answered | 1/1 | 1 | 1.0 | 1.0 | 1.0 | 0.9002 |
| G09 | exact_term_lookup | answered | 1/1 | 1 | 1.0 | 1.0 | 1.0 | 0.8282 |
| G10 | exact_term_lookup | answered | 1/1 | 1 | 1.0 | 1.0 | 1.0 | 0.9714 |
| G11 | paraphrased | answered | 1/1 | 1 | 1.0 | 1.0 | 1.0 | 0.8286 |
| G12 | paraphrased | answered | 1/1 | 1 | 1.0 | 1.0 | 1.0 | 0.8115 |
| G13 | paraphrased | answered | 1/1 | 1 | 0.95 | 1.0 | 1.0 | 0.6627 |
| G14 | paraphrased | answered | 2/2 | 4 | 0.2 | 1.0 | 1.0 | 0.7552 |
| G15 | multi_part | partial | 4/5 | 1 | 0.0 | 0.0 | 1.0 | 0.9381 |
| G16 | multi_part | answered | 2/2 | 2 | 0.2 | 1.0 | 1.0 | 0.772 |
| G17 | multi_part | answered | 3/3 | 3 | 0.0 | 1.0 | 1.0 | 0.8399 |
| G18 | multi_part | answered | 2/2 | 2 | 0.3333 | 1.0 | 1.0 | 0.8845 |
| G19 | cross_document | answered | 2/2 | 1 | 0.8056 | 1.0 | 1.0 | 0.9179 |
| G20 | cross_document | answered | 2/2 | 2 | 0.0 | 1.0 | 1.0 | 0.9363 |
| G21 | cross_document | answered | 2/2 | 1 | 0.45 | 1.0 | 1.0 | 0.7724 |
| G22 | abstention | abstained | n/a | 0 | - | - | - | - |
| G23 | abstention | abstained | n/a | 0 | - | - | - | - |
| G24 | abstention | abstained | n/a | 0 | - | - | - | - |