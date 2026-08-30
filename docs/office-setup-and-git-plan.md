# Moving to the Office Laptop, and the Git History Plan

Two things this file covers: getting the project running on your work machine,
and creating the PR-driven git history the deliverables require.

---

## Part 1 — Setting up on the office laptop

Your office venv is Python 3.12 with the packages already installed, so most of
this is a no-op. Do it in this order.

### 1. Copy the project

Copy everything **except** these, which are rebuilt locally and must not travel:

```
.venv/          the virtual environment (machine-specific)
storage/        the Chroma index (rebuilt by `catalog-rag ingest`)
logs/           runtime logs
.env            YOUR API KEY - never copy this into a repo or a shared drive
__pycache__/    compiled bytecode
```

Everything else — including `reports/` — must come across. The
Evidence-in-Repo Rule means the reports are the deliverable.

### 2. Check the Python version

```powershell
python --version        # expect 3.12.x
```

### 3. Install

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

`requirements.txt` is pinned to the exact versions from your office package
list, so this should resolve without changes.

> **On `torch`:** `requirements.txt` pins `torch==2.6.0`. On this laptop it was
> installed from the CPU-only index to save ~2 GB:
> ```
> pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
> ```
> If your office machine already has torch 2.6.0, skip it. Only the CPU build is
> needed — nothing here uses a GPU.

### 4. Add your key

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `GOOGLE_API_KEY` (or `GEMINI_API_KEY` — both are accepted).
**`.env` is git-ignored and must never be committed.**

### 5. First run

The first run downloads two models from Hugging Face (~220 MB total) and caches
them:

- `BAAI/bge-small-en-v1.5` — embeddings, ~130 MB
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — reranker, ~90 MB

```powershell
catalog-rag ingest
catalog-rag ask "What warning is required for a button cell battery?"
pytest -m "not requires_llm" -q
```

> **If the office network blocks Hugging Face**, download the two models on a
> machine that can reach it, copy the `~/.cache/huggingface` folder across, and
> set `HF_HUB_OFFLINE=1` in `.env`.

### 6. Regenerate the evidence (optional but recommended)

```powershell
catalog-rag all
```

This rewrites everything in `reports/`. The committed reports were generated on
this laptop; re-running on yours confirms reproducibility (NFR-06). If the
numbers move slightly, that is expected — the RAGAS judge is an LLM.

---

## Part 2 — The git history plan

Section 8.1 lists as **mandatory**:

> PR-driven Git history: at least 3 PR-driven merges (`git merge --no-ff`);
> no direct pushes to main.

This is easy to lose marks on, because it is about *how* the commits were made,
not what they contain. Do this on the office laptop before pushing to GitLab.

### Before you start

```powershell
git init
git branch -M main
```

Confirm `.gitignore` is in place first, then check nothing sensitive is staged:

```powershell
git status
git check-ignore -v .env storage logs
```

`.env`, `storage/` and `logs/` must all show as ignored. **If `.env` appears in
`git status`, stop and fix `.gitignore` before committing anything.** A key in
git history is very hard to remove.

### The baseline commit on main

Keep main's initial commit minimal — just the scaffolding — so the feature
branches carry the real work.

```powershell
git add README.md .gitignore .env.example requirements.txt pyproject.toml
git commit -m "chore: project scaffolding, dependencies and quick-start"
```

### Five feature branches, each merged with --no-ff

`--no-ff` forces a merge commit even when a fast-forward is possible. That merge
commit is what makes the history read as PR-driven.

**Branch 1 — the corpus and the business documentation**

```powershell
git checkout -b feature/corpus-and-docs
git add data/corpus/ docs/business-case.md specs/
git commit -m "feat: add 30-document synthetic corpus and business case

30 synthetic policy documents across five families (listing standards,
category guidelines, safety and labeling, restricted substances, image and
content guidelines) giving 300 individually citable clauses.

Adds the business case and the AC-01..AC-10 acceptance criteria in testable
form."
git checkout main
git merge --no-ff feature/corpus-and-docs -m "Merge PR #1: synthetic corpus and business case"
```

**Branch 2 — ingestion and indexing**

```powershell
git checkout -b feature/ingestion-indexing
git add config/ src/catalog_rag/config.py src/catalog_rag/ingest.py `
        src/catalog_rag/embeddings.py src/catalog_rag/logging_utils.py `
        docs/chunking-strategy.md docs/embedding-selection.md
git commit -m "feat: clause-aware ingestion into a persisted Chroma index (AC-01)

Splits on clause boundaries so a chunk and a citation are the same unit.
Chunk ids are content hashes, which makes re-ingestion idempotent.

Adds the chunking and embedding selection rationale, and externalises every
retrieval parameter into config/config.yaml (NFR-04)."
git checkout main
git merge --no-ff feature/ingestion-indexing -m "Merge PR #2: ingestion and indexing"
```

**Branch 3 — hybrid retrieval**

```powershell
git checkout -b feature/hybrid-retrieval
git add src/catalog_rag/retrieval.py src/catalog_rag/query_transform.py
git commit -m "feat: BM25 + vector retrieval with RRF fusion and reranking (AC-03, AC-04, AC-07)

Runs both retrieval arms, fuses them with Reciprocal Rank Fusion, then reranks
with a local cross-encoder before the top-K reaches the generator.

Adds query transformation: rewrite into policy vocabulary, synonym expansion,
and decomposition of multi-part questions."
git checkout main
git merge --no-ff feature/hybrid-retrieval -m "Merge PR #3: hybrid retrieval, fusion and reranking"
```

**Branch 4 — generation and guardrails**

```powershell
git checkout -b feature/grounded-generation
git add src/catalog_rag/generation.py src/catalog_rag/schemas.py `
        src/catalog_rag/llm.py src/catalog_rag/cli.py `
        app/ docs/guardrails.md docs/pii-policy.md
git commit -m "feat: grounded generation with clause citations and abstention (AC-02, AC-05, AC-06)

Returns a validated Pydantic object carrying the answer, clause-level
citations, applicable guideline, requirement, labeling condition and a
grounding confidence.

Two independent abstention paths: before generation when reranking leaves too
little, and after generation on low confidence or missing citations. Cited
clauses are checked against what was actually retrieved, so invented citations
cannot survive.

Adds the CLI and the Streamlit interface."
git checkout main
git merge --no-ff feature/grounded-generation -m "Merge PR #4: grounded generation, guardrails and interfaces"
```

**Branch 5 — evaluation**

```powershell
git checkout -b feature/evaluation-harness
git add eval/ reports/ tests/ src/catalog_rag/evaluate.py src/catalog_rag/ragas_compat.py `
        docs/failure-taxonomy.md docs/model-selection.md docs/cost-latency.md
git commit -m "feat: RAGAS evaluation harness and two-model comparison (AC-08, AC-09, AC-10)

Adds a 20-question golden set with reference answers and expected clauses,
each entry tagged with the acceptance criteria it exercises.

Computes context precision, context recall, faithfulness and answer relevancy
with a Gemini judge, plus deterministic retrieval-recall and abstention-accuracy
metrics that need no judge and are exactly reproducible.

Commits the RAGAS report, the two-model comparison and sample answers as
evidence artifacts."
git checkout main
git merge --no-ff feature/evaluation-harness -m "Merge PR #5: evaluation harness and committed evidence"
```

### Verify the history

```powershell
git log --graph --oneline --all
git log --merges --oneline
```

You should see **5 merge commits**, comfortably over the required 3. The graph
should show branches diverging from main and merging back, not a straight line.

If `git log --merges` prints nothing, the merges fast-forwarded — you missed
`--no-ff`. Redo them.

### Push to GitLab

```powershell
git remote add origin <your-virtusa-gitlab-url>
git push -u origin main
```

### Final check before the cut-off

```powershell
git log --oneline | wc -l          # several commits, not one
git log --merges --oneline | wc -l # at least 3
git ls-files | Select-String "^\.env$"   # must return NOTHING
git ls-files reports/              # the evidence must be tracked
pytest -q                          # tests pass
```

The `.env` check is the important one. If it returns anything, your API key is
in the repository and you should rotate the key immediately.
