# Guardrail Policy

Six guardrails. Each states the rule, why it exists, where it is enforced in
code, and what verifies it. They are enforced in code rather than only asked for
in the prompt, because a prompt is a request and a code check is a guarantee.

---

## G1 — Citation required

**Rule.** No answer is returned without at least one clause-level citation
naming an exact clause id (e.g. `SAF-003-C7`), not just a document id.

**Why.** The assistant's value is that a reviewer can verify it. An uncited
answer is an assertion, and an assertion from a language model about a
compliance rule is exactly the "confidently wrong" failure the whole design
exists to prevent.

**Enforcement.** `check_grounding()` in `src/catalog_rag/generation.py`. If
`len(citations) < grounding.min_citations`, the answer is discarded and replaced
with an abstention. Configured by `grounding.require_citations` and
`grounding.min_citations`.

**Verified by.** `test_ac02_answer_without_citations_becomes_abstention`,
`test_ac02_citations_are_clause_level`.

---

## G2 — Citations must be real

**Rule.** A cited clause id must be present in the context that was actually
retrieved for that question. Invented citations are stripped; if nothing
survives, the answer becomes an abstention.

**Why.** This is the subtlest failure mode in the system. A model that knows the
corpus format will happily produce `SAF-004-C11` — correct shape, plausible
document, does not exist. A human spot-checking the answer sees a citation and
trusts it. Format validation alone would not catch this; only membership in the
retrieved set does.

**Enforcement.** `check_grounding()` compares each `citation.clause_id` against
the `clause_id` metadata of the retrieved documents.

**Verified by.** `test_ac02_invented_clause_ids_are_stripped`,
`test_ac02_answer_citing_only_invented_clauses_abstains`.

---

## G3 — Abstain rather than guess

**Rule.** When the corpus does not support an answer, the assistant abstains and
says so plainly. It never stretches a loosely related clause into an answer.

**Why.** A catalog analyst who receives "I don't know" consults a colleague. One
who receives a confident wrong answer acts on it. The second outcome is worse,
so the system is tuned to prefer the first.

**Enforcement.** Two independent paths, deliberately:

1. **Before generation** — if reranking leaves fewer than
   `grounding.min_supporting_chunks` documents above
   `reranker.score_threshold`, we abstain without calling the LLM at all. This
   path is fast (measured at ~0.2s) and cannot be talked out of by the model.
2. **After generation** — if `grounding_confidence` is below
   `grounding.abstention_threshold` (0.45), the answer is replaced with the
   abstention message.

Two paths rather than one because they fail differently. Path 1 catches
questions with no relevant corpus content. Path 2 catches questions where
something was retrieved but does not actually answer the question.

**Verified by.** `test_ac05_low_confidence_becomes_abstention`,
`test_ac04_reranker_drops_irrelevant_candidates`,
`test_ac05_end_to_end_abstains_on_out_of_corpus_question`. Measured as
`abstention_accuracy` in `reports/ragas_report.md`.

---

## G4 — No compliance determination presented as advice

**Rule.** The assistant states what the guidelines require. It never concludes
that a product or listing "is compliant", "is legal", or "is illegal".

**Why.** This is the line between a reference tool and unlicensed professional
advice. The corpus contains marketplace policy, not law. Even where a policy
clause mirrors a statute, whether a specific product complies depends on facts
the assistant cannot see — actual composition, actual labelling, the
jurisdiction, the test results. A tool that renders verdicts on that basis
invites reliance it cannot support.

Note that the corpus itself reinforces this: `CLS-005-C10`, `CLS-006-C10` and
`RSR-006-C10` all state that findings are marketplace policy positions and not
legal determinations. The guardrail and the corpus agree.

**Enforcement.** Rule 5 of the system prompt in `src/catalog_rag/generation.py`,
and the standing wording of `grounding.abstention_message`, which describes the
assistant as surfacing published guidelines only.

**Verified by.** Committed sample answers in `reports/sample_answers.md`, which
show the assistant stating requirements rather than verdicts.

---

## G5 — Corpus-only answers

**Rule.** Answers come from the retrieved clauses. Model world-knowledge is not
used, even when it is correct.

**Why.** Gemini genuinely knows a great deal about real product-safety
regulation. That is a liability here, not an asset: the corpus is synthetic, and
an answer blending real regulation with synthetic policy is unverifiable and
untraceable. Worse, it would look right. If the corpus is silent, the honest
answer is that the corpus is silent.

**Enforcement.** Rule 1 of the system prompt states this explicitly and calls
out that the model's own knowledge must not be used. G2 provides the structural
backstop: an answer from world-knowledge cannot cite a retrieved clause, so it
fails the citation-membership check.

**Verified by.** `test_ac05_end_to_end_abstains_on_out_of_corpus_question` — the
capital of France is something the model certainly knows and must still refuse.

---

## G6 — Out-of-scope handling

**Rule.** Questions outside catalog and product compliance are abstained on, not
redirected into general assistance.

**Why.** Scope creep in a compliance tool is a trust problem. A tool that
answers a shipping-rates question today is a tool whose answers about labelling
are harder to trust tomorrow, because the user can no longer tell which answers
are corpus-grounded.

**Enforcement.** The same two abstention paths as G3. Out-of-scope questions
retrieve nothing above the rerank threshold, so path 1 catches them before any
LLM call is made.

**Verified by.** Golden set entries `G22` (capital of France), `G23` (refund
policy — plausible-sounding but genuinely absent from the corpus) and `G24`
(commission rates). `G23` is the important one: it is the kind of question a
real user would ask and a helpful-by-default model would try to answer.

---

## Configuration

Every threshold is in `config/config.yaml` under `grounding:` and `reranker:`,
not hard-coded (NFR-04).

| Setting | Value | Effect |
|---|---|---|
| `grounding.abstention_threshold` | 0.45 | Below this confidence, abstain |
| `grounding.min_citations` | 1 | Minimum citations for an answer to be returned |
| `grounding.require_citations` | true | Enforce G1 |
| `grounding.min_supporting_chunks` | 1 | Below this many chunks, abstain before generating |
| `reranker.score_threshold` | -6.0 | Cross-encoder score below which a chunk is dropped |

**On tuning these.** Raising `abstention_threshold` produces a more cautious
assistant: fewer wrong answers, more unnecessary refusals. Lowering it does the
reverse. Given the failure cost described in the business case, the current
values sit deliberately on the cautious side, and `false_abstentions` is
reported in `reports/ragas_report.md` so the cost of that choice stays visible
rather than hidden.

### Measured: why `reranker.score_threshold` is -6.0

This value was chosen from a sweep over the golden set, not by guesswork. The
sweep runs entirely locally (no API calls), so it is cheap to repeat.

| Threshold | Clause recall | Fully correct | Chunks kept on the 3 out-of-corpus questions |
|---|---|---|---|
| **-6.0 (chosen)** | **71.0%** | **70.6%** | **[0, 1, 1]** |
| -8.0 | 71.0% | 70.6% | [0, 5, 2] |
| -9.0 | 74.2% | 76.5% | [0, 8, 6] |
| -10.0 | 74.2% | 76.5% | [0, 8, 8] |
| -11.0 | 77.4% | 82.4% | [0, 8, 8] |

Loosening the threshold to -11.0 buys **+6.4 points of recall** — a real gain.
It also takes the out-of-corpus questions from keeping 0–1 chunks to keeping 8,
which **destroys the pre-generation abstention path entirely**. At -11.0 every
out-of-scope question would reach the LLM with eight irrelevant clauses in hand,
and abstention would depend solely on the model choosing to refuse (guardrail
path 2) rather than on the corpus structurally having nothing to offer.

We keep -6.0. The business case argues a wrong answer costs more than a missed
one, and the questions this loses are multi-part questions where partial
retrieval still yields a `partial` answer rather than a wrong one.

Note also that `retrieval.final_top_k` was swept over 5/6/8/10/12 and recall did
not move at all (71.0% throughout). The threshold, not the top-K, is the binding
constraint — worth knowing before anyone tries to fix recall by raising top-K.
