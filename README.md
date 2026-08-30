# Product Catalog & Compliance Assistant

A retrieval-augmented assistant that answers catalog and product-compliance
questions **grounded strictly in a synthetic policy corpus**, cites the exact
clause it used, and **abstains when the corpus does not support an answer**.

**Business Case AAIE_021_ECM** · E-commerce — Catalog & Product Compliance ·
Gen AI Core + RAG Engineering

---

## What it does

Ask a question in plain English:

```
catalog-rag ask "What warning is required for a product with a button cell battery?"
```

```
ANSWERED
The product, its packaging and the listing must carry the ingestion hazard
warning stating that the product contains a button or coin cell battery, that
swallowing can lead to chemical burns, perforation of soft tissue and death,
and that immediate medical attention must be sought.

Applicable guideline   SAF-003-C7
Requirement            Reproduce the ingestion hazard warning on the product,
                       its packaging and the listing.
Labeling / safety      Must also state to keep batteries out of reach of
                       children and dispose of used batteries immediately.

Citations
  SAF-003-C7   Battery and Electrical Safety Labeling Requirements

confidence 1.00 · 25.1s · gemini-3.5-flash
```

Ask something the corpus does not cover, and it refuses rather than inventing:

```
catalog-rag ask "What is the capital of France?"
```

```
ABSTAINED
The committed catalog and compliance corpus does not contain a guideline that
supports an answer to this question.
```

---

## Quick start

**Requirements:** Python 3.11+ (developed and tested on 3.12), pip, and a Google
Gemini API key. No Docker, no database server.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS / Linux

# 2. Install
pip install -r requirements.txt
pip install -e .

# 3. Add your Gemini API key
copy .env.example .env           # Windows  (cp on macOS / Linux)
# then edit .env and set GOOGLE_API_KEY

# 4. Build the index from the committed corpus
catalog-rag ingest

# 5. Ask a question
catalog-rag ask "What labeling is required for cosmetics?"
```

### One command for everything (NFR-02)

```bash
catalog-rag all
```

Runs ingestion, the RAGAS evaluation and the two-model comparison, writing every
artifact into `reports/`.

### Optional web interface

```bash
streamlit run app/streamlit_app.py
```

Shows the answer, the citations, and the retrieved clauses with their fusion and
rerank scores.

---

## All commands

| Command | What it does |
|---|---|
| `catalog-rag ingest` | Build the vector index from the corpus (AC-01) |
| `catalog-rag ingest --rebuild` | Delete the index and rebuild from scratch |
| `catalog-rag ask "..."` | Ask a question (add `--show-context` for the retrieved clauses) |
| `catalog-rag search "..."` | Show retrieval results only, no LLM call — useful for debugging |
| `catalog-rag evaluate` | Golden set + RAGAS, writes `reports/` (AC-08, AC-09) |
| `catalog-rag compare` | Compare two Gemini models (AC-10) |
| `catalog-rag all` | Everything above, in order |
| `pytest` | Run the test suite |
| `pytest -m acceptance -v` | Run only the AC-traceability tests (one per criterion) |

---

## How it works

```
question
   |
   v
[1] Query transformation ............... Gemini      (AC-07)
    rewrite into policy vocabulary, expand with
    synonyms, decompose multi-part questions
   |
   +--------------------+
   |                    |
   v                    v
[2a] BM25 search    [2b] Vector search ... local     (AC-03)
     exact terms,        paraphrase,
     clause ids,         intent
     chemical names
   |                    |
   +--------+-----------+
            v
[3] Reciprocal Rank Fusion ............. local       (AC-03)
    merge by rank, not by score
            |
            v
[4] Cross-encoder reranking ............ local       (AC-04)
    read query and passage together,
    drop anything below threshold
            |
            v
[5] Grounded generation ................ Gemini      (AC-02, AC-06)
    validated Pydantic object with
    clause-level citations
            |
            v
[6] Guardrail checks ................... local       (AC-02, AC-05)
    citations present? citations real?
    confidence above threshold?
            |
            v
       answer or abstention
```

**Only steps 1 and 5 call an API.** Embeddings, search, fusion, reranking and
the guardrail checks all run locally.

### Why two retrieval arms

Compliance questions split cleanly into two kinds, and neither method handles
both:

- *"What is the DEHP limit?"* — exact terms. **BM25** finds it; embeddings often
  do not.
- *"What goes on the box for a toy with a coin battery?"* — meaning. **Vector
  search** finds it; BM25 does not.

RRF merges the two by rank rather than score, because a BM25 score and a cosine
similarity are on incomparable scales and cannot simply be added.

---

## Project layout

```
config/config.yaml          every tunable parameter (NFR-04)
data/corpus/                30 synthetic policy documents, 300 clauses
docs/                       business case, chunking, embeddings, guardrails,
                            PII policy, cost/latency, failure taxonomy,
                            model selection
specs/                      acceptance criteria in testable form
eval/golden_set.json        20 questions with reference answers (AC-08)
reports/                    committed evidence: RAGAS report, model comparison
src/catalog_rag/
    config.py               loads config.yaml
    ingest.py               parse -> chunk -> embed -> Chroma      (AC-01)
    embeddings.py           local Sentence-Transformers adapter
    retrieval.py            BM25 + vector + RRF + rerank           (AC-03, AC-04)
    query_transform.py      rewrite / expand / decompose           (AC-07)
    generation.py           grounded generation + guardrails       (AC-02, AC-05)
    schemas.py              Pydantic structured output             (AC-06)
    evaluate.py             RAGAS harness + model comparison       (AC-09, AC-10)
    cli.py                  command line runner (argparse)
app/streamlit_app.py        optional web interface
tests/test_acceptance.py    one test per acceptance criterion
```

---

## The corpus

30 synthetic documents, 300 individually citable clauses, in five families:

| Prefix | Family | Docs |
|---|---|---|
| `CLS` | Listing standards | 6 |
| `CAT` | Category guidelines | 6 |
| `SAF` | Safety & labeling | 6 |
| `RSR` | Restricted substances | 6 |
| `IMG` | Image & content guidelines | 6 |

Each clause has a stable id like `SAF-003-C7`. That id is the chunk boundary,
the metadata key, the citation the model must produce, and the unit the golden
set grades against.

**All data is synthetic.** It was written for this project and must not be used
as real compliance guidance. See [docs/pii-policy.md](docs/pii-policy.md).

---

## Technology

| Layer | Choice | Why |
|---|---|---|
| Orchestration | LangChain / LCEL | Approved stack |
| LLM | Google Gemini (`gemini-3.5-flash`) | Only approved provider |
| Embeddings | `BAAI/bge-small-en-v1.5`, local | [docs/embedding-selection.md](docs/embedding-selection.md) |
| Vector store | Chroma, in-process | No Docker, no server |
| Lexical | `rank_bm25` via LangChain `BM25Retriever` | Exact-term matching |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local, no hosted reranker needed |
| Evaluation | RAGAS, judge = Gemini | Approved stack |
| Interface | Typer CLI + Streamlit | Section 6.1 |

---

## Documentation

| Document | Covers |
|---|---|
| [docs/business-case.md](docs/business-case.md) | Problem, users, corpus, guardrails, success metrics |
| [specs/acceptance-criteria.md](specs/acceptance-criteria.md) | AC-01 to AC-10 in testable form, with traceability |
| [docs/chunking-strategy.md](docs/chunking-strategy.md) | Why clause-aware chunking, and what was rejected |
| [docs/embedding-selection.md](docs/embedding-selection.md) | MTEB-informed model choice and trade-offs |
| [docs/guardrails.md](docs/guardrails.md) | The six guardrails and where each is enforced |
| [docs/pii-policy.md](docs/pii-policy.md) | Synthetic data, masking, what leaves the machine |
| [docs/failure-taxonomy.md](docs/failure-taxonomy.md) | Retrieval vs grounding vs synthesis failures |
| [docs/model-selection.md](docs/model-selection.md) | Two-model comparison and rationale |
| [docs/cost-latency.md](docs/cost-latency.md) | Cost and latency of a representative query |

---

## Known environment issue

`ragas 0.4.3` imports `langchain_community.chat_models.vertexai`, a module that
`langchain-community 0.4.2` removed. Both versions are fixed by the approved
stack, so neither can simply be changed.
`src/catalog_rag/ragas_compat.py` registers a stub under that name before ragas
is imported. Ragas only needs the symbol to exist; this project uses Gemini and
never touches Vertex AI.
