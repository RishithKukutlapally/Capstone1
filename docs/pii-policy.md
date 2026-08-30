# Data and PII Policy

Satisfies NFR-03: all data is synthetic, any PII is synthetic and masked where
shown, and none is ever written to logs in plaintext.

---

## 1. All corpus data is synthetic

Every one of the 30 documents in `data/corpus/` was written for this project.
There is no real seller, product, or confidential catalog data anywhere in the
repository, and no Virtusa confidential data (Synthetic-Data Rule).

The documents are written in the register of real marketplace policy and cite
plausible technical values (a 31.7 mm small-parts cylinder, a 0.009% lead
limit). They are not reproductions of any real policy document, and the
document ids, version numbers, owners and effective dates are all invented.

**They must not be used as a source of real compliance guidance.** They exist to
exercise a retrieval pipeline.

## 2. No PII in the corpus

The corpus contains no personal data at all. It refers to roles — "the seller",
"the buyer", "the catalog operations policy owner" — never to individuals.
There are no names, addresses, emails, phone numbers or account identifiers.

This is a design choice, not an accident: PII in the corpus would end up in
embeddings, in the vector store, in retrieved context, and in prompts sent to
Gemini. Keeping it out at the source is the only reliable control.

## 3. PII may appear in user queries

The one place personal data can realistically enter the system is a user typing
it into a question:

> "Why was seller SELLER-AB12CD34's listing for order ORD-99887766 rejected?
> They emailed from rishi.test@example.com"

We cannot prevent this, so we handle it.

## 4. Masking

`mask_pii()` in `src/catalog_rag/logging_utils.py` runs over every question and
answer before it is written to disk.

| Pattern | Replaced with |
|---|---|
| Email addresses | `[EMAIL]` |
| Order references (`ORD-`, `ORDER-`, `SO-` + digits) | `[ORDER_ID]` |
| Seller identifiers (`SELLER-` + alphanumeric) | `[SELLER_ID]` |
| Phone numbers (9+ digits, optional country code) | `[PHONE]` |

The example above is written to the log as:

```
"Why was seller [SELLER_ID]'s listing for order [ORDER_ID] rejected?
 They emailed from [EMAIL]"
```

**Clause ids are deliberately preserved.** `SAF-003-C7` and `RSR-001-C4` look
superficially like identifiers but are citations, and masking them would destroy
the provenance trail that NFR-08 requires. This is explicitly tested by
`test_nfr03_pii_is_masked_but_clause_ids_survive`.

## 5. What is logged, and where

| File | Contents | Committed? |
|---|---|---|
| `logs/interactions.jsonl` | One record per question: masked question, masked answer, citations, abstention flag, confidence, model | **No** — `logs/` is git-ignored |
| `logs/catalog_rag.log` | Application events | **No** — git-ignored |
| `reports/*` | Evaluation artifacts built from the synthetic golden set | **Yes** — required by the Evidence-in-Repo Rule |

Logs stay local. The committed reports contain only synthetic golden-set
questions, so there is no masking concern there.

## 6. What leaves the machine

Worth being precise about, because most of this system is local.

| Component | Runs | Data sent externally |
|---|---|---|
| Embeddings (`bge-small-en-v1.5`) | Locally | None |
| Vector store (Chroma) | Locally, in-process | None |
| BM25 | Locally, in memory | None |
| Reranker (`ms-marco-MiniLM-L-6-v2`) | Locally | None |
| Query transformation | **Google Gemini API** | The user's question |
| Answer generation | **Google Gemini API** | The question plus the retrieved clauses |
| RAGAS judging | **Google Gemini API** | Golden-set questions, answers and contexts |

Only the Gemini calls leave the machine. The corpus is synthetic and the queries
are masked in logs, but note that **masking applies to logs, not to the prompt**
— the raw question is what gets sent to Gemini, because masking it would
degrade retrieval and answer quality.

If this system were ever pointed at a real corpus, that is the first thing to
revisit: either mask before the provider call and accept the quality cost, or
use a self-hosted model for generation.

## 7. Secrets

NFR-01. The Gemini API key is read from the environment or from `.env`, which is
git-ignored. `.env.example` is committed with a placeholder and no real key.
`tests/test_acceptance.py` asserts that no file in `src/` or `.env.example`
contains a string beginning `AIza`, which is the Google API key prefix.
