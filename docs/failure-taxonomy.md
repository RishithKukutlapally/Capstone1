# Failure Taxonomy

Where this pipeline goes wrong, separated by the stage the failure originates
in. The distinction matters because each class has a different fix, and
mislabelling one as another sends you optimising the wrong component.

| Class | Definition | Fix lives in |
|---|---|---|
| **Retrieval failure** | The clause that answers the question never reached the generator | Chunking, the two arms, fusion, reranking |
| **Grounding failure** | The right clause was retrieved, but the answer misrepresents it or cites it wrongly | Prompt, guardrails, structured output |
| **Synthesis failure** | Clauses were retrieved and used faithfully, but combined into a poor answer | Prompt, decomposition, context ordering |
| **False abstention** | The corpus had the answer, but the guardrails refused anyway | Thresholds, upstream retrieval |
| **Infrastructure failure** | The pipeline broke and never learned whether the corpus had the answer | Quota, retries, error handling |

The last two are not part of the classic triad, but both were observed in this
project and both are dangerous specifically because they *masquerade* as correct
behaviour. §4b is the most instructive failure here and is worth reading even if
the rest is skimmed.

The single most useful diagnostic question is: **was the answering clause in the
retrieved set?** If no, it is a retrieval failure and no amount of prompt work
will help. If yes, the problem is downstream.

---

## 1. Retrieval failures

*The generator was never given what it needed.*

Measured as `retrieval_recall` in `reports/ragas_report.md` — of the clauses the
golden set expects, how many actually reached the generator — and by RAGAS
**context recall**.

### 1a. Multi-part questions retrieve only the loudest part

**The dominant retrieval failure in this corpus.** A question asking about
magnets *and* coin cells *and* lead limits produces a single embedding that sits
between all three topics and is close to none of them. The clauses for the
first-mentioned topic dominate the top-K and the rest are crowded out.

Measured directly, with the **raw** question and no query transformation, over
the 17 answerable golden entries: **86.2% clause recall (25/29)**, with 14 of 17
questions fully correct.

The residual failures are concentrated exactly where predicted — multi-part and
vocabulary-mismatched questions:

| Entry | Type | Result | Why |
|---|---|---|---|
| G14 | *"what do I need to show buyers about what is inside a shampoo?"* | **0 of 2** | Vocabulary mismatch — see §1b. Retrieval returns **nothing**, so this becomes a false abstention (§4) |
| G16 | 2-part: approval + plug labelling | 1 of 2 | `CAT-001-C6` missed; the retrieved `IMG-004-C7` points at it but is the image rule, not the labelling rule |
| G15 | 3-part: magnets + coin cell + lead limit | 4 of 5 | `RSR-001-C4` (lead limit) crowded out — three topics competing for five slots |

Every other entry scored full marks. The failure is specific and structural, not
diffuse noise.

**G15 illustrates the structural limit plainly.** `retrieval.final_top_k` is 5,
so five chunks are returned. A question spanning three topics cannot be fully
covered in five slots unless ranking is perfect. Raising the top-K does not fix
it (see §1d) — the answer is decomposition, which gives each sub-question its
own top-5.

### A note on how this number was produced

The answer key for three entries was **revised after inspecting retrieval
output**, which is a thing worth being explicit about, since loosening your own
grading after seeing results is how an evaluation stops meaning anything. Each
revision is recorded in a `key_note` field on the entry, and
`test_ac08_revised_answer_keys_are_documented` fails if a revised key lacks one.

| Entry | Original | Revised | Justification |
|---|---|---|---|
| G15 | required `SAF-002-C6`, `SAF-002-C7`, `SAF-003-C6`, `SAF-003-C7` | accepts `CAT-003-C6` / `CAT-003-C7` as alternatives | The corpus states these rules **twice** — in the SAF safety documents and restated in the CAT-003 toys guideline, which cross-references them **by clause id**. An answer citing either is correct. |
| G12 | required `CAT-005-C7` **and** `CAT-005-C8` | requires `CAT-005-C8` only | `CAT-005-C8` lists "cures acne" explicitly as prohibited and answers the question alone. `CAT-005-C7` is the underlying principle, moved to `supporting_clauses` (not scored). |
| G03 | required `RSR-001-C3` **and** `RSR-001-C4` | requires `RSR-001-C4` only | `RSR-001-C4` states the lead limit. `RSR-001-C3` explains how a concentration is measured — background, not the answer. |

The raw-key figure was 71.0%. The corrected-key figure is 86.2%. **The system's
behaviour did not change; only the measurement did.** G16 was deliberately left
as a genuine miss even though a retrieved clause cross-references the expected
one, because `IMG-004-C7` is the image requirement rather than the labelling
requirement — it points at the rule without stating it, so it is not an
equivalent citation.

**Mitigation:** AC-07 query decomposition. Each sub-question is retrieved
independently and all result lists are fused together, so every part gets its
own shot at the index rather than competing inside one embedding. The final
recall figure in `reports/ragas_report.md` is measured with decomposition
active.

**Residual risk:** decomposition is itself an LLM call and can split a question
badly. `query_transform.max_sub_queries` caps the blast radius, and a transform
failure falls back to the original question rather than breaking the pipeline.

### 1b. Vocabulary mismatch

The user writes "kids toy"; the corpus says "toy intended for children under 36
months". The vector arm handles most of this, but not all.

**Mitigation:** the rewrite step maps casual phrasing into policy vocabulary
before retrieval, and expansion terms are appended to feed the BM25 arm.

### 1c. Exact identifiers lost to tokenisation

A user quotes `SAF-003-C7`. A naive tokeniser splits it into `saf`, `003`, `c7`
— three tokens that match almost everything and identify nothing.

**Mitigation:** `tokenize()` in `retrieval.py` extracts clause-id patterns
before word-splitting and keeps them whole. Covered by
`test_ac03_tokenizer_keeps_clause_ids_whole`.

### 1d. Reranker discards a correct-but-oddly-phrased clause

The cross-encoder threshold (`reranker.score_threshold: -6.0`) is what makes
abstention possible, but it can also drop a genuinely relevant clause whose
wording does not resemble the question. This is a deliberate trade: the
threshold is the abstention mechanism, so loosening it to rescue these cases
would weaken AC-05.

**Detection:** a golden entry whose expected clause appears in the fused list but
not the final list. Visible by comparing `catalog-rag search` output against the
`rerank_score` column.

### 1e. Cross-referenced clauses are not followed

The corpus deliberately cross-references — `CAT-003-C7` points at `SAF-003-C7`.
Retrieval is single-hop, so it can return the pointer without the target.

**Not mitigated.** Multi-hop retrieval was out of scope. In practice the two
arms plus fusion usually surface both, because cross-referencing clauses share
vocabulary with their targets, but this is a genuine architectural limit rather
than something the current design solves.

---

## 2. Grounding failures

*The right clause was present, but the answer misuses it.*

Measured by RAGAS **faithfulness** and by the citation checks in
`check_grounding()`.

### 2a. Invented clause ids

The highest-severity failure in the system, and the least visible. A model that
has seen the corpus format will produce `SAF-004-C11` — right shape, plausible
document, does not exist. A reviewer who sees a citation assumes it was checked.

Format validation alone does not catch this. Only membership does.

**Mitigation:** `check_grounding()` compares every cited `clause_id` against the
clause ids actually retrieved for that question. Non-members are stripped; if
nothing survives, the answer becomes an abstention. Covered by
`test_ac02_invented_clause_ids_are_stripped`.

### 2b. Answering from model knowledge

Gemini knows a great deal about real product-safety regulation. Asked about lead
limits it can answer correctly *without reading the corpus at all* — and the
answer will look right while being untraceable to any committed clause.

**Mitigation:** prompt rule 1 forbids it explicitly. The structural backstop is
2a: an answer from world-knowledge cannot cite a retrieved clause, so it fails
the membership check.

### 2c. Overstating a conditional rule

Corpus clauses are heavily conditional — a warning is required *if* the toy is
for over-36-months *and* contains a small part. Dropping a condition turns
"required in these circumstances" into "always required".

**Partially mitigated.** Clause-aware chunking helps by keeping each rule whole
with its conditions attached, rather than splitting the condition away from the
obligation. RAGAS faithfulness is the metric that detects the residual.

### 2d. Compliance determination presented as advice

Answering "yes, your listing is compliant" rather than "the guideline requires
X". Guardrail G4 in `docs/guardrails.md`.

**Mitigation:** prompt rule 5. Note this is the one guardrail enforced by prompt
alone — it is a judgement about tone and framing that no code check can reliably
make. That makes it the weakest link in the guardrail set, and the reason the
committed sample answers matter as evidence.

---

## 3. Synthesis failures

*Correct clauses, faithfully used, but a poor answer.*

Measured by RAGAS **answer relevancy**.

### 3a. Partial answers reported as complete

A three-part question where the corpus covers two parts, answered as though all
three were addressed. The user has no signal that a third of their question went
unanswered.

**Mitigation:** the `PARTIAL` status in `AnswerStatus`, and prompt rule 4, which
requires the model to name the part the corpus does not cover.

### 3b. Context dilution — measured

The per-question scores in `reports/ragas_report.md` show this clearly. Context
precision splits by question type:

| Question type | Context precision |
|---|---|
| Single-clause lookup (G01, G03) | 1.0 |
| Exact-term lookup (G07–G10) | 1.0 |
| Paraphrased (G11–G13) | 0.95–1.0 |
| **Multi-part (G15, G17, G20)** | **0.0–0.33** |

The average of 0.6435 is produced almost entirely by the multi-part questions.

The cause is structural rather than a defect. A three-part question retrieves
five chunks to cover three topics, so for any one sub-topic two or three of those
chunks are irrelevant and precision falls — while **context recall stays at 1.0
and faithfulness stays at 1.0**, meaning the answer is still complete and
correct. Precision is being traded for coverage, deliberately.

Lowering `final_top_k` would raise precision and lower recall on exactly the
questions that most need coverage. Given the business case weights a wrong
answer above an incomplete one, the current setting is the right side of that
trade.

### 3c. Context dilution

Passing five clauses when one answers the question invites the model to weave in
tangential material, which lowers relevancy without lowering faithfulness — the
answer is *true* but padded.

**Mitigation:** `retrieval.final_top_k: 5` after threshold filtering, so weak
candidates are dropped rather than padded in. There is a real tension here: a
smaller top-K improves precision and relevancy but risks recall on multi-part
questions.

### 3c. Burying the answer

Leading with scope and definitions instead of the requirement. A style failure,
but a real one for a user scanning for an answer.

**Mitigation:** the prompt asks for plain language aimed at a catalog operations
analyst, and the separate `requirement` field forces the obligation out into its
own structured field where it cannot be buried.

---

## 4. False abstention

Worth calling out separately, because it is a failure of the *guardrails* rather
than of retrieval, grounding or synthesis — and because it is the cost of the
system's caution.

The pipeline abstains when the corpus **does** contain the answer. Causes: a
retrieval failure upstream (§1) leaving nothing above threshold, or a model
under-reporting `grounding_confidence` below the 0.45 threshold.

Tracked as `false_abstentions` in `reports/ragas_report.md`, deliberately
reported alongside `abstention_accuracy` so the trade is visible in both
directions rather than only the flattering one.

**On tuning.** Raising `grounding.abstention_threshold` reduces wrong answers and
increases false abstentions; lowering it does the reverse. The business case
argues that a wrong answer costs more than a refusal here, so the thresholds sit
deliberately on the cautious side. That is a judgement about this domain, not a
universal setting.

---

## 4b. Infrastructure failure — and why it must not look like abstention

A fourth class, outside the retrieval/grounding/synthesis triad, because it does
not originate in any of them: **the pipeline broke and never found out whether
the corpus supports an answer.**

This was found the hard way, and it is the most instructive failure in the
project.

### What happened

During an evaluation run, `gemini-3.5-flash` exhausted its daily quota at
question 12. The remaining thirteen questions returned
`429 RESOURCE_EXHAUSTED`.

The pipeline caught those exceptions and returned `make_abstention(...)`, so
every failure was recorded with `status: abstained` and
`grounding_confidence: 0.00`. The report then read:

```
abstention_accuracy    1.0        <- looks perfect
citation_rate          1.0        <- looks perfect
false_abstentions      10         <- looks like a tuning problem
```

Every one of those numbers is wrong in a way that flatters the system. A run
where **half the questions never reached the model at all** presented as a
cautious, well-behaved assistant with a slightly conservative threshold. The
natural next action — lowering `abstention_threshold` — would have been
completely misguided.

### How it was caught

Not by the metrics, which looked plausible. By the **per-question latency
column**: every "abstention" from G12 onward took ~220 seconds, while the
genuine abstention (G22, capital of France) took 0.0 seconds because it never
called the API. A real abstention is fast. A 220-second abstention is a timeout
wearing an abstention's clothes.

Worth noting the diagnostic principle: the failure was invisible in the
aggregate metrics and obvious in the per-question detail. That is the argument
for committing `per_question` records in `reports/ragas_report.json` rather than
summary numbers alone.

### The fix

1. `AnswerStatus.ERROR` is now distinct from `AnswerStatus.ABSTAINED`.
   `make_error()` is returned on provider failure; `make_abstention()` is
   reserved for the corpus genuinely not supporting an answer.
2. `score_deterministic()` **excludes errored questions** from every quality
   metric and reports `pipeline_errors` and `errored_ids` separately. A non-zero
   `pipeline_errors` means the run is not trustworthy.
3. `score_with_ragas()` **raises rather than writing `nan`**. The earlier run
   wrote four `nan` values into the report, which is the absence of a
   measurement presented as a measurement.
4. `catalog-rag doctor` and a fail-fast quota check in `run_evaluation()` stop a
   long run before it starts rather than after it has produced a bad report.

Regression-tested by
`test_nfr05_provider_failure_is_an_error_not_an_abstention`.

### The general lesson

**A safe fallback must not be indistinguishable from a correct answer.** NFR-05
asks for graceful degradation, and returning an abstention on failure *is*
graceful — but it silently destroyed the evaluation's meaning. Degrading
gracefully for the user and recording honestly for the system are two separate
requirements, and the first must not be implemented at the cost of the second.

---

## 5. How to diagnose a specific bad answer

```bash
# 1. Was the answering clause retrieved at all?
catalog-rag search "the question"

#    Not in the list          -> retrieval failure (section 1)
#    In the list              -> continue

# 2. Look at the full pipeline output
catalog-rag ask "the question" --show-context

#    Clause retrieved but not cited        -> grounding failure (2a, 2b)
#    Cited but the answer misstates it     -> grounding failure (2c)
#    Cited and stated correctly, but the
#    answer is unhelpful or incomplete     -> synthesis failure (section 3)
#    Abstained despite the clause being
#    right there                           -> false abstention (section 4)
```

The two commands exist for exactly this: `search` isolates retrieval from
generation, which is what makes the retrieval-versus-grounding distinction
observable rather than a guess.
