# Embedding Model Selection

**Chosen:** `BAAI/bge-small-en-v1.5` — 384 dimensions, 33M parameters, ~130 MB,
512-token context, runs locally on CPU via Sentence-Transformers.

Configured under `embeddings:` in `config/config.yaml`.

---

## 1. Constraints that narrowed the field

| Constraint | Consequence |
|---|---|
| Open-source Sentence-Transformers only (approved stack) | Rules out OpenAI, Cohere, Voyage embeddings |
| Runs with pip + Python, no Docker, no service | Must be a local model that fits in process memory |
| Must run on a standard corporate laptop, CPU-only | Rules out 7B embedding models |
| Corpus is English policy text, ~300 chunks | A small model has ample capacity; 300 vectors is a tiny index |
| Re-embedded on every corpus change | Encoding speed matters for the developer loop |

## 2. Candidates compared

MTEB (Massive Text Embedding Benchmark) retrieval scores, English subset. These
are the published leaderboard figures used to shortlist, not measurements taken
in this project.

| Model | Dim | Params | Size | MTEB Retrieval (avg) | CPU encode speed | Verdict |
|---|---|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | 22M | 90 MB | ~41.9 | Fastest | Baseline. Symmetric training hurts it on short-query/long-passage retrieval, which is exactly our shape. |
| **`BAAI/bge-small-en-v1.5`** | **384** | **33M** | **130 MB** | **~51.7** | **Fast** | **Chosen.** ~10 MTEB points over MiniLM for 40 MB more. |
| `intfloat/e5-small-v2` | 384 | 33M | 130 MB | ~49.0 | Fast | Very close second. Slightly behind BGE on retrieval; needs `query:`/`passage:` prefixes. |
| `BAAI/bge-base-en-v1.5` | 768 | 109M | 440 MB | ~53.2 | ~3× slower | +1.5 MTEB for 3× encode time and 2× index width. Poor trade at this corpus size. |
| `intfloat/e5-large-v2` | 1024 | 335M | 1.3 GB | ~55.9 | ~10× slower | Best accuracy, but a 1.3 GB download and slow CPU encoding for +4 points on a 300-chunk index. |

## 3. Why bge-small-en-v1.5

**1. Asymmetric training matches our retrieval shape.** BGE is trained with a
query instruction prefix so short questions and long passages land in
compatible regions of the space. Our queries are 10–25 word questions; our
passages are 100–300 word clauses. MiniLM, trained symmetrically on sentence
pairs, is measurably weaker on this asymmetry — which is where most of the
10-point MTEB gap comes from.

The prefix is applied in `src/catalog_rag/embeddings.py` and configured as
`embeddings.query_instruction`. Passages get no prefix, per the model card.
Omitting the query prefix costs roughly 1–2 points of retrieval accuracy, so it
is set explicitly rather than left to chance.

**2. The dimensionality trade lands on the small side here.** 384 dims × ~300
chunks is a trivial index (~0.5 MB). Moving to 768 doubles index width and
triples encode time for +1.5 MTEB points. On a 300-chunk corpus, retrieval
quality is dominated by chunking and reranking, not by the last point of
embedding accuracy — so the compute is better spent on the cross-encoder, which
is where §5 shows the real gain is.

**3. It leaves headroom for the reranker.** The end-to-end budget on a CPU
laptop is what matters, not the embedding step in isolation. `bge-small` at ~40 ms
per query leaves room for the cross-encoder's ~200 ms over 12 candidates and
still returns in under a second. `e5-large` would consume that budget alone.

**4. 512-token context covers our chunks.** Our largest chunk is ~1400
characters ≈ 350 tokens, comfortably inside the window, so nothing is silently
truncated. This is worth checking rather than assuming — truncation at the
embedding step is invisible and degrades recall in ways that are hard to
diagnose.

**5. Cost.** Zero marginal cost and zero data egress. Corpus content never
leaves the machine; only the final prompt goes to Gemini. For a compliance tool
that is an architectural property worth having, not just a cost saving.

## 4. Normalisation and distance

`embeddings.normalize: true` produces unit vectors, and Chroma is configured
with `hnsw:space: cosine`. With normalised vectors cosine similarity and inner
product are equivalent, and the score range is a stable [-1, 1] — which matters
because thresholds tuned against an unnormalised score would drift as the corpus
changes.

## 5. Where the retrieval quality actually comes from

Worth stating plainly, because it justifies spending less on embeddings:

| Component | Contribution |
|---|---|
| Clause-aware chunking | Largest single factor. Clean boundaries mean a retrieved chunk is one complete rule. |
| BM25 arm | Carries exact-match queries (clause ids, chemical names, numeric thresholds) that embeddings systematically miss. |
| Cross-encoder reranking | Largest accuracy gain per unit of compute. Reads query and passage jointly. |
| Embedding model choice | Real but smallest of the four. |

Choosing `bge-small` and spending the saved compute on the cross-encoder is the
better allocation at this corpus size.

## 6. Revisit conditions

This choice should be re-examined if:

- the corpus grows past ~10,000 chunks, where embedding precision starts to
  dominate and `bge-base` becomes worth its cost;
- the corpus becomes multilingual, which `bge-small-en` does not handle at all —
  `bge-m3` would be the replacement;
- a GPU becomes available in the target environment, which removes most of the
  argument against the larger models.
