# Sample Answers

Model: `gemini-3.5-flash` · Embeddings: `BAAI/bge-small-en-v1.5` · Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2`

Committed evidence for AC-02 and AC-05, taken from the golden-set run in
`reports/ragas_report.json`. Every answered question carries at least one
clause-level citation; the refusals at the end show the assistant declining
rather than inventing an answer.

Answered: 15 · Refused: 5

---

## Answered, with clause-level citations (AC-02)

### G01 — What warning text is required for a product that contains a button or coin cell battery?

**Confidence:** 1.00 · **Latency:** 24.2s

A product containing a button or coin cell battery must carry the following warning on the product itself, its packaging, and its listing: "WARNING: INGESTION HAZARD — This product contains a button or coin cell battery. Swallowing can lead to chemical burns, perforation of soft tissue, and death. Seek immediate medical attention." Additionally, the warning must state that batteries should be kept out of reach of children and that used batteries must be disposed of immediately.

**Citations:** `SAF-003 SAF-003-C7`

**Clauses retrieved:** `SAF-003-C7`, `CAT-003-C7`, `SAF-003-C5`, `SAF-003-C6`, `SAF-003-C1`

---

### G03 — What is the maximum concentration of lead allowed in an accessible material of a children's product?

**Confidence:** 1.00 · **Latency:** 13.4s

The maximum concentration of lead allowed in any accessible material of a product intended for children is 0.009 percent by weight.

**Citations:** `RSR-001 RSR-001-C4`

**Clauses retrieved:** `RSR-001-C4`, `RSR-004-C1`, `RSR-005-C6`, `CAT-006-C10`, `RSR-002-C6`

---

### G07 — What is the concentration limit for the sum of DEHP, DBP and BBP in plasticised material?

**Confidence:** 1.00 · **Latency:** 10.2s

The sum of the restricted phthalates DEHP, DBP, and BBP must not exceed 0.1 percent by weight in any plasticised material.

**Citations:** `RSR-001 RSR-001-C5`

**Clauses retrieved:** `RSR-001-C5`, `RSR-004-C1`, `CAT-006-C10`, `RSR-002-C5`, `RSR-001-C3`

---

### G08 — What is the chromium VI limit in leather that touches the skin?

**Confidence:** 1.00 · **Latency:** 25.2s

The chromium VI limit in leather articles in contact with the skin is 3 milligrams per kilogram.

**Citations:** `RSR-003 RSR-003-C5`

**Clauses retrieved:** `RSR-003-C5`, `RSR-004-C1`, `RSR-001-C6`, `RSR-003-C1`, `RSR-001-C7`

---

### G09 — What is the magnetic flux index threshold above which a loose magnet is prohibited in a toy?

**Confidence:** 1.00 · **Latency:** 14.5s

The magnetic flux index threshold above which a loose or detachable magnet is prohibited in a toy is 50 kG²mm² or greater.

**Citations:** `SAF-002 SAF-002-C6`

**Clauses retrieved:** `SAF-002-C6`, `CAT-003-C6`, `CAT-003-C8`, `SAF-002-C7`, `SAF-002-C8`

---

### G10 — What are the dimensions of the small parts cylinder?

**Confidence:** 1.00 · **Latency:** 7.5s

The dimensions of the small parts cylinder are a diameter of 31.7 millimetres and a depth of 57.1 millimetres measured at the shallowest point.

**Citations:** `SAF-002 SAF-002-C1`

**Clauses retrieved:** `SAF-002-C1`

---

### G11 — Can I put 'free shipping' and 'best seller' in my product name?

**Confidence:** 1.00 · **Latency:** 9.3s

No, you cannot include "free shipping" or "best seller" in your product name. Product titles are prohibited from containing promotional claims, shipping terms, price references, or urgency language. Including these terms is classified as a Tier 1 defect and will result in the listing being suppressed from search.

**Citations:** `CLS-001 CLS-001-C6`

**Clauses retrieved:** `CLS-001-C6`, `CLS-001-C7`, `RSR-006-C4`, `IMG-001-C7`, `CLS-002-C9`

---

### G12 — Is it okay for a face cream listing to say the product cures acne?

**Confidence:** 1.00 · **Latency:** 10.9s

No, a face cream listing is not permitted to claim that the product 'cures acne'. Under the guidelines, this specific claim is explicitly prohibited for cosmetics, and any claims to treat, heal, or prevent a medical condition reclassify the product as a medicine, which is prohibited in the cosmetics category.

**Citations:** `CAT-005 CAT-005-C8`, `CAT-005 CAT-005-C7`

**Clauses retrieved:** `CAT-005-C8`, `CAT-005-C7`, `CAT-005-C10`, `RSR-002-C2`, `RSR-002-C10`

---

## Refused — the corpus does not support an answer (AC-05)

### G13 — A seller wants to sell a toy with tiny pieces to two year olds. Is that allowed?

**Status:** `abstained` · **Confidence:** 0.00 · **Citations:** 0

The committed catalog and compliance corpus does not contain a guideline that supports an answer to this question. Please consult the catalog operations policy owner. This assistant surfaces published guidelines only and does not issue compliance determinations.

**Clauses retrieved:** `SAF-002-C2`, `CAT-003-C5`, `SAF-002-C3`, `RSR-005-C9`, `SAF-002-C4`

---

### G15 — For a children's toy that contains both magnets and a coin cell battery, what warnings do I need on the listing, and what is the lead limit for the materials?

**Status:** `abstained` · **Confidence:** 0.00 · **Citations:** 0

The committed catalog and compliance corpus does not contain a guideline that supports an answer to this question. Please consult the catalog operations policy owner. This assistant surfaces published guidelines only and does not issue compliance determinations.

**Clauses retrieved:** `SAF-003-C7`, `CAT-003-C7`, `SAF-003-C5`, `SAF-003-C6`, `IMG-004-C5`

---

### G22 — What is the capital of France?

**Status:** `abstained` · **Confidence:** 0.00 · **Citations:** 0

The committed catalog and compliance corpus does not contain a guideline that supports an answer to this question. Please consult the catalog operations policy owner. This assistant surfaces published guidelines only and does not issue compliance determinations.

**Clauses retrieved:** _none — nothing passed the relevance threshold_

---

### G23 — What is the marketplace's refund window for a buyer who received a damaged item?

**Status:** `abstained` · **Confidence:** 0.00 · **Citations:** 0

The committed catalog and compliance corpus does not contain a guideline that supports an answer to this question. Please consult the catalog operations policy owner. This assistant surfaces published guidelines only and does not issue compliance determinations.

**Clauses retrieved:** `CAT-005-C4`, `CLS-001-C10`, `SAF-001-C9`

---

### G24 — What commission rate does the marketplace charge sellers in the electronics category?

**Status:** `abstained` · **Confidence:** 0.00 · **Citations:** 0

The committed catalog and compliance corpus does not contain a guideline that supports an answer to this question. Please consult the catalog operations policy owner. This assistant surfaces published guidelines only and does not issue compliance determinations.

**Clauses retrieved:** `CAT-001-C1`, `CAT-001-C4`, `CAT-001-C5`, `CAT-001-C8`, `CAT-001-C7`

---
