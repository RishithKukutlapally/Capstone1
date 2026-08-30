import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from catalog_rag.config import get_config
from catalog_rag.generation import answer_question

st.set_page_config(page_title="Catalog & Compliance Assistant", layout="centered")
st.title("Product Catalog & Compliance Assistant")
st.caption("Ask about listing standards, category rules, safety labeling, or restricted substances.")

cfg = get_config()

def show(value):
    return value if value else "—"

question = st.text_input(
    "Question",
    placeholder="What warning is required for a product with a button cell battery?",
)
go = st.button("Ask")

if go and question.strip():
    with st.spinner("Retrieving clauses and generating a grounded answer..."):
        result = answer_question(question.strip())

    answer = result.answer

    text = answer.answer
    for citation in answer.citations:
        if citation.clause_id and citation.clause_id in text:
            text = text.replace(citation.clause_id, f"**{citation.clause_id}**")

    st.subheader("Answer")
    if answer.status.value == "answered":
        st.markdown(text)
    elif answer.status.value == "abstained":
        st.warning(text)
    else:
        st.error(text)

    st.write(
        f"**Guideline:** {show(answer.applicable_guideline)}  |  "
        f"**Requirement:** {show(answer.requirement)}"
    )
    st.write(f"**Labeling / safety condition:** {show(answer.labeling_safety_condition)}")
    st.caption(
        f"status {answer.status.value} · confidence {answer.grounding_confidence:.2f} · "
        f"{result.latency_seconds:.1f}s · {result.model}"
    )

    st.subheader("Citations")
    if not answer.citations:
        st.write("None — the assistant abstained.")
    for citation in answer.citations:
        st.write(f"**{citation.clause_id}** — {citation.doc_title or citation.doc_id}")
        if citation.quote:
            st.caption(citation.quote)

    st.subheader("Retrieved clauses")
    if not result.retrieved:
        st.write("No clauses passed the relevance threshold.")
    for i, chunk in enumerate(result.retrieved, 1):
        st.write(
            f"[{i}] **{chunk.clause_id}** {chunk.clause_title}  ·  "
            f"rrf {chunk.rrf_score:.4f}  ·  rerank {chunk.rerank_score}"
        )
