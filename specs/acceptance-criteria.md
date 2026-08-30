# Acceptance Criteria — Testable Form

Every criterion below names the artifact that satisfies it and the test or
golden-set entry that verifies it (AC-Traceability Rule).

Traceability works two ways:

1. **Tests.** Every test lives in `tests/test_acceptance.py`, one per criterion, marked `@pytest.mark.acceptance` and its
   name contains the AC id, e.g. `test_ac01_ingestion_is_complete_and_idempotent`.
2. **Golden set.** Each entry in `eval/golden_set.json` carries an
   `acceptance_criteria` list naming the AC ids it exercises.

Verify traceability at any time with:

```bash
pytest -m acceptance -v
python -m catalog_rag.cli trace
```

---

## AC-01 — Ingestion into a persisted, idempotent index

**Criterion.** The system ingests a synthetic corpus of ≥ 30 documents into a
persisted vector index. Ingestion is re-runnable and idempotent.

**Given** the 30 documents in `data/corpus/`
**When** `catalog-rag ingest` is run twice in a row
**Then** the corpus reports ≥ 30 distinct `doc_id` values, the Chroma collection
is persisted under `storage/chroma/`, and the vector count after the second run
equals the count after the first.

**How.** Chunk ids are a hash of `doc_id | clause_id | part | text`, so an
unchanged corpus produces an identical id set and the second run rewrites the
same rows rather than appending new ones.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/ingest.py` |
| Test | `tests/test_acceptance.py::test_ac01_ingestion_is_complete_and_idempotent` |

---

## AC-02 — Grounded answer with ≥ 1 clause-level citation

**Criterion.** A user can ask a natural-language question and receive an answer
grounded only in the corpus, with at least one clause-level citation
(document + section / clause id) per answer.

**Given** a question the corpus covers, e.g. *"What warning is required for a
product containing a button cell battery?"*
**When** the pipeline answers it
**Then** `status` is `answered`, `citations` is non-empty, and every citation's
`clause_id` matches the pattern `^[A-Z]{3}-\d{3}-C\d{1,2}$` and exists in the
corpus.

**How.** `grounding.require_citations` and `grounding.min_citations` in
`config/config.yaml` are enforced after generation. An answer that returns no
citation is converted to an abstention rather than shown.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/generation.py`, `src/catalog_rag/schemas.py` |
| Test | `tests/test_acceptance.py::test_ac02_answers_must_carry_real_clause_level_citations` |
| Golden set | entries tagged `AC-02` |

---

## AC-03 — Hybrid retrieval with fusion

**Criterion.** Retrieval combines lexical (BM25) and semantic search and fuses
the two result sets before generation.

**Given** the query *"DEHP concentration limit"*
**When** retrieval runs
**Then** the BM25 arm and the vector arm each return candidates independently,
and the fused list is ordered by Reciprocal Rank Fusion score
`sum(weight / (rrf_k + rank))`, not by either arm's raw score.

**How.** `retrieve()` calls both arms and passes their ranked lists to `rrf()`.
Raw BM25 scores and cosine similarities are on incomparable scales, so fusion is
rank-based by design.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/retrieval.py` |
| Test | `tests/test_acceptance.py::test_ac03_both_search_arms_run_and_are_fused_with_rrf` |
| Golden set | entries tagged `AC-03` |

---

## AC-04 — Reranking before generation

**Criterion.** Retrieved candidates are reranked before the top-K is passed to
the generator.

**Given** `retrieval.fusion_top_k` fused candidates
**When** the cross-encoder reranks them
**Then** every candidate carries a `rerank_score`, candidates scoring below
`reranker.score_threshold` are dropped, and at most
`retrieval.final_top_k` candidates reach the generator.

**How.** A bi-encoder embeds query and passage separately; a cross-encoder reads
the pair jointly and can therefore judge whether the passage actually answers
the question, not just whether it is topically near it.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/retrieval.py` |
| Test | `tests/test_acceptance.py::test_ac04_candidates_are_reranked_before_generation` |
| Golden set | entries tagged `AC-04` |

---

## AC-05 — Abstention when the corpus is insufficient

**Criterion.** When the corpus does not support an answer, the system abstains
or flags low confidence rather than fabricating.

**Given** an out-of-corpus question, e.g. *"What is the capital of France?"* or
*"What is our return policy for damaged goods?"* (no returns policy exists in
the corpus)
**When** the pipeline answers it
**Then** `status` is `abstained`, `answer` is the configured abstention message,
and `citations` is empty.

**Two independent abstention paths:**
1. **Pre-generation** — reranking leaves fewer than
   `grounding.min_supporting_chunks` candidates above threshold, so no LLM call
   is made at all.
2. **Post-generation** — the model returns `grounding_confidence` below
   `grounding.abstention_threshold`, or returns no citations.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/generation.py` |
| Test | `tests/test_acceptance.py::test_ac05_abstains_when_the_corpus_cannot_support_an_answer` |
| Sample output | `reports/sample_answers.md` (refusal example) |
| Golden set | entries tagged `AC-05` |

---

## AC-06 — Validated structured output

**Criterion.** Answers are returned as a validated structured object containing
answer text, citations, applicable guideline, the requirement, any labeling /
safety condition, and a grounding / confidence indicator.

**Given** any question
**When** the pipeline answers it
**Then** the result validates against the `GroundedAnswer` Pydantic model with
fields: `answer`, `status`, `citations`, `applicable_guideline`, `requirement`,
`labeling_safety_condition`, `grounding_confidence` (0.0–1.0), `reasoning`.

**How.** The model is bound with LangChain's `.with_structured_output()`, so
the schema is enforced at the provider call. A response that fails validation
falls back to abstention instead of reaching the user.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/schemas.py` |
| Test | `tests/test_acceptance.py::test_ac06_output_is_a_validated_object_with_the_required_fields` |
| Golden set | entries tagged `AC-06` |

---

## AC-07 — Query transformation

**Criterion.** Multi-part or ambiguous queries are transformed (rewrite /
expansion / decomposition) before retrieval.

**Given** a multi-part question, e.g. *"For a kids' toy with magnets and a coin
battery, what warnings do I need and what's the lead limit?"*
**When** query transformation runs
**Then** it produces a rewritten query in policy vocabulary plus 2–3 sub-queries
(at most `query_transform.max_sub_queries`), each sub-query is retrieved
independently, and all arms are fused together.

**Given** a short single-clause question
**Then** decomposition is skipped (below
`query_transform.min_chars_for_decomposition`) to avoid a needless LLM call.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/query_transform.py` |
| Test | `tests/test_acceptance.py::test_ac07_queries_are_transformed_before_retrieval` |
| Golden set | entries tagged `AC-07` |

---

## AC-08 — Committed golden evaluation set

**Criterion.** A golden evaluation set of ≥ 20 questions with reference answers
/ expected contexts is committed with a re-runnable scoring script.

**Given** `eval/golden_set.json`
**Then** it holds ≥ 20 entries, each with `id`, `question`, `reference_answer`,
`expected_clauses`, `acceptance_criteria`, and `category`; and
`catalog-rag evaluate` regenerates the metrics from it.

| Evidence | Location |
|---|---|
| Dataset | `eval/golden_set.json` |
| Script | `src/catalog_rag/evaluate.py` |
| Test | `tests/test_acceptance.py::test_ac08_golden_set_is_committed_and_valid` |

---

## AC-09 — RAGAS metrics computed and committed

**Criterion.** RAGAS metrics (context precision, context recall, faithfulness,
answer relevancy) are computed and the numeric results committed as a report
artifact.

**Given** the golden set and a configured Gemini judge
**When** `catalog-rag evaluate` runs
**Then** `reports/ragas_report.json` and `reports/ragas_report.md` are written
with a numeric value for each of the four metrics.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/evaluate.py` |
| Report | `reports/ragas_report.json`, `reports/ragas_report.md` |
| Test | `tests/test_acceptance.py::test_ac09_ragas_report_is_committed_with_real_numbers` |

---

## AC-10 — Two-model comparison

**Criterion.** At least two candidate LLMs are evaluated on the custom eval set
and a comparison (metrics + selection rationale) is committed.

**Given** `eval.comparison_models` in config (`gemini-2.5-flash`,
`gemini-2.5-pro`)
**When** `catalog-rag compare` runs
**Then** each model is scored on the same golden set with the same retrieval
context, and `reports/model_comparison.md` records per-model metrics, latency,
and a written selection rationale.

**Controlled variable:** retrieval is identical across models. Only the
generator changes, so any metric difference is attributable to the model.

| Evidence | Location |
|---|---|
| Implementation | `src/catalog_rag/evaluate.py` |
| Report | `reports/model_comparison.md`, `reports/model_comparison.json` |
| Test | `tests/test_acceptance.py::test_ac10_two_models_are_compared_with_a_rationale` |

---

## Non-Functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-01 | No secrets committed; env config with `.env.example` | `.env.example`, `.gitignore`, `tests/test_acceptance.py::test_nfr01_no_secrets_are_committed` |
| NFR-02 | End-to-end from a single documented command | `README.md` quick-start, `catalog-rag all` |
| NFR-03 | Synthetic data; PII masked, never logged plaintext | `docs/pii-policy.md`, `tests/test_acceptance.py::test_nfr03_pii_is_masked_but_clause_ids_survive` |
| NFR-04 | Retrieval params externalized in config | `config/config.yaml`, `tests/test_acceptance.py::test_nfr04_retrieval_parameters_live_in_config_not_in_code` |
| NFR-05 | Retries and graceful failure on provider errors | `src/catalog_rag/llm.py`, `tests/test_acceptance.py::test_ac05_abstains_when_the_corpus_cannot_support_an_answer` |
| NFR-06 | Every quality claim reproducible | `src/catalog_rag/evaluate.py`, committed golden set |
| NFR-07 | Cost / latency noted at concept level | `docs/cost-latency.md` |
| NFR-08 | Query/answer logging with provenance | `src/catalog_rag/logging_utils.py`, `logs/interactions.jsonl` |
