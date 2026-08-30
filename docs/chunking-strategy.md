# Chunking Strategy and Rationale

**Chosen strategy:** clause-aware splitting with a recursive character fallback.
Configured as `chunking.strategy: clause_aware_recursive` in `config/config.yaml`.
Implemented in `src/catalog_rag/ingest.py`.

---

## 1. The decision in one sentence

**One clause = one chunk**, because the clause is the unit the answer must cite,
and a chunk boundary that does not match the citation boundary makes
clause-level citation (AC-02) unsound.

## 2. Why not fixed-size chunking

The obvious approach is a 512-token sliding window. It fails here for a specific,
demonstrable reason.

Consider this run of text in `SAF-002`:

```
### SAF-002-C2 Under 36 Months Prohibition
A toy intended for children under 36 months shall not contain ... This is an
absolute prohibition, not a labelling obligation.

### SAF-002-C3 Over 36 Months Labelling Obligation
A toy intended for children of 36 months and over that contains a small part
shall carry a choking hazard warning ...
```

A fixed-size window lands mid-way and produces a chunk containing the tail of
C2 and the head of C3. Now the retriever returns one chunk covering **two
contradictory rules** — an absolute prohibition and a labelling obligation — and
the generator has to guess which clause id to cite. Whichever it picks, the
citation is partly wrong, and a reviewer following it lands on the wrong rule.

That is not a hypothetical edge case in this corpus. Adjacent clauses are
frequently a prohibition followed by its exception, which is precisely the pair
you must not blur.

## 3. What we do instead

**Step 1 — split on clause headings.** Every `### CLS-001-C4 Title` heading
starts a new chunk. The clause id, its title, and the `##` section it sits under
are captured as metadata. This makes the chunk boundary and the citation
boundary the same boundary, by construction.

**Step 2 — recursive fallback for long clauses only.** A clause longer than
`max_chunk_chars` (1400) is split with LangChain's
`RecursiveCharacterTextSplitter` at `chunk_size` 900 with `chunk_overlap` 150,
preferring paragraph then line then sentence breaks. Each part keeps the parent
clause id, so a split clause still cites as one clause. In this corpus roughly
5% of clauses hit this path.

**Step 3 — breadcrumb prefix.** Every chunk is prefixed with:

```
Battery and Electrical Safety Labeling Requirements > 2. Button and Coin Cells > SAF-003-C7 Required Button Cell Warning
```

This matters more than it looks. Clause text often says "the warning shall state
..." without repeating what product it applies to — that context lives in the
document title and the section heading. Without the breadcrumb, the embedding
for C7 contains no signal that it is about button cells, and a semantic search
for "coin battery warning" misses it. The breadcrumb puts the hierarchy into the
vector.

## 4. Parameter choices

| Parameter | Value | Why |
|---|---|---|
| `max_chunk_chars` | 1400 | Above this, a clause is long enough that a retriever returning it wastes generator context on irrelevant sub-parts. 95% of clauses are shorter and stay whole. |
| `chunk_size` | 900 | Only applies inside an oversized clause. Roughly 200–230 tokens — comfortably inside `bge-small`'s 512-token window with headroom for the breadcrumb. |
| `chunk_overlap` | 150 | ~17% overlap. Enough that a requirement split across the boundary appears whole in one part; small enough not to inflate the index. |
| `prepend_breadcrumb` | true | See §3, step 3. |

## 5. Resulting index shape

| Measure | Value |
|---|---|
| Documents | 30 |
| Clauses | 300 |
| Chunks | see `catalog-rag ingest` output |
| Chunks per document | ~10 |

Chunks are near-uniform in size because clauses are, which keeps BM25's length
normalisation well-behaved — a genuine secondary benefit of splitting on the
document's own structure rather than on a character count.

## 6. Alternatives considered

| Strategy | Why not |
|---|---|
| **Fixed-size (512 tokens)** | Breaks citation integrity. See §2. |
| **Whole-document chunks** | 30 vectors for a 30-document corpus. Retrieval degenerates to document selection, and the generator receives ~4000 words of which ~40 are relevant — precisely the context dilution that produces unfaithful answers. |
| **Semantic (embedding-similarity) chunking** | Finds boundaries by embedding drift. This corpus already has explicit, authored boundaries that are more reliable than inferred ones, and semantic chunking would produce boundaries that do not align with clause ids. Cost without benefit here. It would be the right call on unstructured prose. |
| **Sentence-window (retrieve sentence, expand to neighbours)** | Genuinely attractive, and the closest runner-up. Rejected because "expand to neighbouring sentences" crosses clause boundaries, reintroducing exactly the problem in §2. Our breadcrumb gives most of the context benefit without the boundary risk. |
| **Parent-document retrieval** | Retrieve small, generate from the parent document. Adds an index and a lookup for a corpus whose clauses are already self-contained. |

## 7. Metadata schema

Every chunk carries:

| Field | Example | Used for |
|---|---|---|
| `doc_id` | `SAF-003` | Citation, filtering |
| `doc_title` | `Battery and Electrical Safety Labeling Requirements` | Citation display |
| `doc_type` | `safety_labeling` | Filtering by policy family |
| `category` | `Electronics, Toys, Novelty` | Category-aware filtering |
| `version` | `3.0` | Provenance |
| `section` | `2. Button and Coin Cells` | Citation display |
| `clause_id` | `SAF-003-C7` | **The citation anchor** |
| `clause_title` | `Required Button Cell Warning` | Citation display |
| `source_file` | `SAF-003-battery-...md` | Traceability to file |
| `citation` | `SAF-003 SAF-003-C7` | Pre-built label the generator quotes |

`citation` is pre-rendered at ingest rather than assembled at generation time,
so the model copies a string instead of composing one. Models compose citation
strings badly; they copy them reliably.
