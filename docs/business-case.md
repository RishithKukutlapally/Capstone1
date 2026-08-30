# Business Case — Product Catalog & Compliance Assistant

**Business Case ID:** AAIE_021_ECM
**Domain:** E-commerce — Catalog & Product Compliance
**Type:** Gen AI Capstone — Gen AI Core + RAG Engineering

---

## 1. Problem

A marketplace's catalog-operations team answers the same kinds of question every
day, for thousands of listings:

- *"What labeling is required for a toy that contains a coin cell battery?"*
- *"Does a title that says 'FREE SHIPPING — BEST SELLER' meet our standards?"*
- *"What is the lead limit in a children's product?"*
- *"Can a cosmetic listing say 'cures acne'?"*

The answers exist. They are spread across five families of policy document —
listing standards, category guidelines, product-safety and labeling
requirements, restricted-substances rules, and image / content guidelines — and
finding the right clause takes minutes of manual searching per question. At
catalog scale that is the bottleneck.

Worse, an agent who half-remembers a rule and answers from memory creates a real
cost: a wrongly-suppressed listing costs the seller revenue, and a wrongly-
approved one is a safety exposure.

**So the failure mode we are engineering against is not "slow". It is
"confidently wrong".** A system that answers 70% of questions with an exact
clause citation and says "I don't know" to the other 30% is far more useful than
one that answers 100% of them plausibly.

## 2. Target Users

| User | What they need | How they use the assistant |
|---|---|---|
| **Catalog operations analyst** | The exact clause governing a listing, fast | Asks a natural-language question, reads the answer, opens the cited clause to confirm before acting |
| **Seller support agent** | To explain a rejection to a seller in the seller's own terms | Asks why a listing was flagged, quotes the cited clause back to the seller |
| **Category compliance reviewer** | To confirm the labeling set for a product family | Asks a multi-part question covering labeling plus substance limits |
| **Policy owner** | To find where a rule is stated, and whether it conflicts with another | Asks about a concept and sees every clause that touches it |

None of these users are lawyers, and none of them should treat the output as a
compliance determination. That constraint shapes the guardrails in §5.

## 3. Corpus

30 synthetic policy documents, all written for this project. No real seller,
product, or confidential catalog data is used anywhere (Synthetic-Data Rule).

| Family | Prefix | Docs | Covers |
|---|---|---|---|
| Listing standards | `CLS` | 6 | Titles, descriptions, attributes, pricing, defect tiers, prohibited items |
| Category guidelines | `CAT` | 6 | Electronics, apparel, toys, food & supplements, cosmetics, household chemicals |
| Safety & labeling | `SAF` | 6 | General safety, choking/mechanical, battery/electrical, dangerous goods, flammability, label format |
| Restricted substances | `RSR` | 6 | Framework & general limits, cosmetics, textiles, electronics, food-contact & toys, disclosure & claims |
| Image & content | `IMG` | 6 | Primary images, secondary images, authenticity, category-specific, moderation, accessibility |

**Structure.** Every document has YAML frontmatter (`doc_id`, `title`,
`doc_type`, `category`, `version`, `effective_date`, `owner`), numbered `##`
sections, and numbered `###` clauses with stable ids in the form
`CLS-001-C4`. That gives **300 individually citable clauses**.

The clause id is the backbone of the whole system: it is the chunk boundary, the
metadata key, the citation the model must produce, and the unit the golden set
grades against. Documents deliberately cross-reference each other
(`CAT-003-C7` points at `SAF-003-C7`), which is what makes multi-hop and
decomposition questions meaningful rather than artificial.

## 4. Success Metrics

| Metric | Target | Where measured |
|---|---|---|
| Context precision | ≥ 0.70 | `reports/ragas_report.md` |
| Context recall | ≥ 0.75 | `reports/ragas_report.md` |
| Faithfulness | ≥ 0.85 | `reports/ragas_report.md` |
| Answer relevancy | ≥ 0.80 | `reports/ragas_report.md` |
| Correct abstention on out-of-corpus questions | 100% of the abstention golden entries | `reports/ragas_report.md` |
| Citations per answered question | ≥ 1, clause-level | enforced in code, checked by tests |

Faithfulness is weighted highest because of the failure mode in §1: an unfaithful
answer is worse than no answer here.

## 5. Domain Guardrails

Stated in full, with the enforcing code, in [guardrails.md](guardrails.md). In summary:

1. **Citation-required.** No answer is returned without at least one clause-level
   citation. An answer that fails this check is converted to an abstention.
2. **Abstain over guess.** If retrieval returns nothing above threshold, or the
   model's grounding confidence is below `grounding.abstention_threshold`, the
   system abstains and says so.
3. **No compliance determination.** The assistant surfaces the applicable rule.
   It never states that a listing "is compliant" or "is illegal", and every
   answer carries a standing disclaimer. This is not a style choice — it is the
   line between a reference tool and unlicensed advice.
4. **Corpus-only.** The prompt forbids using model world-knowledge. If the
   corpus is silent, the correct answer is that the corpus is silent.
5. **Out-of-scope handling.** Questions outside catalog compliance (weather,
   general chit-chat, other domains) are abstained on, not redirected to
   general knowledge.
6. **No PII in logs.** Queries are masked before being written
   ([pii-policy.md](pii-policy.md)).

## 6. Why RAG and not fine-tuning

Policy changes. `CAT-005` is at version 2.6 and will be at 2.7 next quarter. A
fine-tuned model would need retraining on every amendment and would still be
unable to cite the clause it used. Retrieval means a policy update is a corpus
edit plus a re-ingest, and the citation falls out of the architecture for free.

## 7. Scope Boundary

**In scope:** ingestion, chunking, indexing, hybrid retrieval, fusion,
reranking, query transformation, grounded generation with citations, structured
output, abstention, RAGAS evaluation, two-model comparison, CLI and Streamlit
interfaces.

**Out of scope:** connecting to a real catalog system, taking listing actions,
any real or confidential data, fine-tuning, building a vector database engine,
deployment, authentication, and front-end polish.
