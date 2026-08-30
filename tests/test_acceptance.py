import json
import re

import pytest

from catalog_rag.config import PROJECT_ROOT, get_config, project_path
from catalog_rag.generation import check_grounding, make_abstention, make_error
from catalog_rag.ingest import ingest, make_chunks
from catalog_rag.logging_utils import mask_pii
from catalog_rag.retrieval import fuse_with_rrf, get_bm25, get_store, retrieve, tokenize
from catalog_rag.schemas import AnswerStatus, Citation, GroundedAnswer

from langchain_core.documents import Document

CLAUSE_ID = re.compile(r"^[A-Z]{3}-\d{3}-C\d{1,2}$")

def golden_set() -> dict:
    return json.loads(project_path(get_config().paths.golden_set_path).read_text(encoding="utf-8"))

def fake_doc(clause_id: str) -> Document:
    return Document(
        id=clause_id,
        page_content=f"text of {clause_id}",
        metadata={"clause_id": clause_id, "doc_id": clause_id[:7],
                  "doc_title": "Test Doc", "section": "1", "clause_title": "Test",
                  "citation": f"{clause_id[:7]} {clause_id}"},
    )

@pytest.mark.acceptance
def test_ac01_ingestion_is_complete_and_idempotent():
    corpus = list(project_path(get_config().paths.corpus_dir).glob("*.md"))
    assert len(corpus) >= 30, f"AC-01 needs >= 30 documents, found {len(corpus)}"

    chunks = make_chunks()
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique or chunks are silently lost"

    assert ids == [c.id for c in make_chunks()], "chunk ids are not deterministic"

    for chunk in chunks:
        for field in ("doc_id", "clause_id", "clause_title", "citation", "doc_type"):
            assert chunk.metadata.get(field), f"chunk {chunk.id} is missing {field}"

    result = ingest()
    assert result["vectors_before"] == result["vectors_after"], "ingestion is not idempotent"

@pytest.mark.acceptance
def test_ac02_answers_must_carry_real_clause_level_citations():
    docs = [fake_doc("SAF-003-C7")]

    good = GroundedAnswer(
        answer="The ingestion hazard warning is required.",
        citations=[Citation(doc_id="SAF-003", clause_id="SAF-003-C7")],
        grounding_confidence=0.9,
    )
    kept = check_grounding(good, docs)
    assert not kept.abstained
    assert CLAUSE_ID.match(kept.citations[0].clause_id), "citation must name a clause, not just a doc"

    uncited = GroundedAnswer(answer="Some answer.", citations=[], grounding_confidence=0.9)
    assert check_grounding(uncited, docs).abstained

    invented = GroundedAnswer(
        answer="Some answer.",
        citations=[Citation(doc_id="SAF-999", clause_id="SAF-999-C1")],
        grounding_confidence=0.9,
    )
    assert check_grounding(invented, docs).abstained

@pytest.mark.acceptance
def test_ac03_both_search_arms_run_and_are_fused_with_rrf():
    cfg = get_config()
    question = "button cell battery ingestion warning"

    lexical = get_bm25().invoke(question)
    semantic = get_store().similarity_search(question, k=cfg.retrieval.vector_top_k)
    assert lexical, "BM25 arm returned nothing"
    assert semantic, "vector arm returned nothing"

    assert "saf-003-c7" in tokenize("What does SAF-003-C7 require?")

    fused = fuse_with_rrf([[fake_doc("A"), fake_doc("B")]])
    assert fused[0].metadata["rrf_score"] == pytest.approx(1 / (cfg.retrieval.rrf_k + 1), abs=1e-6)

    both = fuse_with_rrf([
        [fake_doc("only_lexical"), fake_doc("both")],
        [fake_doc("only_semantic"), fake_doc("both")],
    ])
    assert both[0].metadata["clause_id"] == "both"

@pytest.mark.acceptance
def test_ac04_candidates_are_reranked_before_generation():
    cfg = get_config()
    docs = retrieve("What warning is required for a button cell battery?")

    assert docs, "retrieval returned nothing for an in-corpus question"
    assert len(docs) <= cfg.retrieval.final_top_k

    scores = [d.metadata["rerank_score"] for d in docs]
    assert scores == sorted(scores, reverse=True), "results are not ordered by rerank score"

@pytest.mark.acceptance
def test_ac05_abstains_when_the_corpus_cannot_support_an_answer():
    cfg = get_config()

    assert retrieve("langgraph websocket kubernetes deployment") == []

    unsure = GroundedAnswer(
        answer="Probably this.",
        citations=[Citation(doc_id="SAF-003", clause_id="SAF-003-C7")],
        grounding_confidence=cfg.grounding.abstention_threshold - 0.1,
    )
    assert check_grounding(unsure, [fake_doc("SAF-003-C7")]).abstained

    abstention = make_abstention("test")
    assert abstention.citations == []
    assert abstention.applicable_guideline == ""

    error = make_error("rate limited")
    assert error.errored and not error.abstained

@pytest.mark.acceptance
def test_ac06_output_is_a_validated_object_with_the_required_fields():
    required = {"answer", "status", "citations", "applicable_guideline",
                "requirement", "labeling_safety_condition", "grounding_confidence"}
    assert required <= set(GroundedAnswer.model_fields)

    assert GroundedAnswer(answer="x", grounding_confidence=85).grounding_confidence == 0.85
    assert GroundedAnswer(answer="x", grounding_confidence=-1).grounding_confidence == 0.0
    assert GroundedAnswer(answer="x", grounding_confidence="bad").grounding_confidence == 0.0

    assert AnswerStatus.ABSTAINED != AnswerStatus.ERROR

@pytest.mark.acceptance
def test_ac07_queries_are_transformed_before_retrieval():
    from catalog_rag.query_transform import TransformedQuery, queries_for_retrieval

    from catalog_rag.query_transform import transform_query
    assert transform_query("Title length?").sub_queries == []

    transformed = TransformedQuery(
        rewritten_query="labelling requirements for button cell batteries",
        sub_queries=["what warning is required", "how must the compartment be secured"],
        expansion_terms=["coin cell", "ingestion hazard"],
    )
    queries = queries_for_retrieval(transformed)
    assert transformed.rewritten_query in queries
    for sub in transformed.sub_queries:
        assert sub in queries
    assert any("coin cell" in q for q in queries)

@pytest.mark.acceptance
def test_ac08_golden_set_is_committed_and_valid():
    data = golden_set()
    questions = data["questions"]
    assert len(questions) >= 20, f"AC-08 needs >= 20 questions, found {len(questions)}"

    real_clauses = {c.metadata["clause_id"] for c in make_chunks()}
    referenced_acs = set()

    for item in questions:
        assert item["question"].strip()
        assert len(item["reference_answer"]) > 40, f"{item['id']} has a thin reference answer"
        assert item["acceptance_criteria"], f"{item['id']} references no AC"
        referenced_acs.update(item["acceptance_criteria"])

        for requirement in item["expected_clauses"]:
            for clause in requirement.split("|"):
                assert CLAUSE_ID.match(clause), f"{clause} is not a valid clause id"
                assert clause in real_clauses, f"{item['id']} expects {clause}, not in the corpus"

    types = {q["question_type"] for q in questions}
    for required in ("exact_term_lookup", "paraphrased", "multi_part", "abstention"):
        assert required in types, f"golden set has no {required} questions"

    assert {"AC-02", "AC-03", "AC-04", "AC-05", "AC-07"} <= referenced_acs

@pytest.mark.acceptance
def test_ac09_ragas_report_is_committed_with_real_numbers():
    path = PROJECT_ROOT / "reports" / "ragas_report.json"
    if not path.exists():
        pytest.skip("No RAGAS report yet. Run `catalog-rag evaluate` to produce it.")

    report = json.loads(path.read_text(encoding="utf-8"))
    metrics = report["ragas_metrics"]

    combined = " ".join(metrics).lower().replace("_", "")
    for expected in ("contextprecision", "contextrecall", "faithfulness", "relevancy"):
        assert expected in combined, f"AC-09 metric {expected} missing from the report"

    for name, value in metrics.items():
        if name == "samples_scored":
            continue
        assert isinstance(value, (int, float)), f"{name} is not numeric"
        assert 0.0 <= value <= 1.0, f"{name} = {value} is out of range"

    for field in ("generator_model", "judge_model", "embedding_model", "retrieval_config"):
        assert report.get(field), f"report does not record {field}"

    assert report["deterministic_metrics"]["pipeline_errors"] == 0, (
        "the run had pipeline errors, so its numbers are not trustworthy"
    )

@pytest.mark.acceptance
def test_ac10_two_models_are_compared_with_a_rationale():
    path = PROJECT_ROOT / "reports" / "model_comparison.json"
    if not path.exists():
        pytest.skip("No comparison yet. Run `catalog-rag compare` to produce it.")

    report = json.loads(path.read_text(encoding="utf-8"))
    assert len(report["models"]) >= 2, "AC-10 needs at least two models"

    for name, scores in report["models"].items():
        assert scores["ragas"], f"{name} has no RAGAS scores"

    assert "identical" in report["note"].lower()

    rationale = PROJECT_ROOT / "docs" / "model-selection.md"
    assert rationale.exists() and len(rationale.read_text(encoding="utf-8")) > 800

def test_nfr01_no_secrets_are_committed():
    assert (PROJECT_ROOT / ".env.example").exists()
    assert re.search(r"^\.env$", (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8"), re.M)

    for path in [PROJECT_ROOT / ".env.example", *(PROJECT_ROOT / "src").rglob("*.py")]:
        assert "AIza" not in path.read_text(encoding="utf-8"), f"possible key in {path.name}"

def test_nfr03_pii_is_masked_but_clause_ids_survive():
    masked = mask_pii("Contact seller@example.com about order ORD-99887766 re CLS-001-C4")
    assert "seller@example.com" not in masked
    assert "ORD-99887766" not in masked

    assert "CLS-001-C4" in masked

def test_nfr04_retrieval_parameters_live_in_config_not_in_code():
    cfg = get_config()
    assert cfg.chunking.chunk_size > 0
    assert cfg.retrieval.bm25_top_k > 0 and cfg.retrieval.vector_top_k > 0
    assert cfg.retrieval.rrf_k > 0 and cfg.retrieval.final_top_k > 0
    assert 0 <= cfg.grounding.abstention_threshold <= 1

    source = (PROJECT_ROOT / "src" / "catalog_rag" / "retrieval.py").read_text(encoding="utf-8")
    assert "cfg.retrieval" in source, "retrieval.py does not read from config at all"
    for hardcoded in ("k=20", "k=5", "[:5]"):
        assert hardcoded not in source, f"retrieval.py hard-codes {hardcoded}"

def test_nfr02_and_docs_required_by_the_rubric_exist():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "catalog-rag ingest" in readme and "pip install" in readme

    for name in ("business-case.md", "chunking-strategy.md", "embedding-selection.md",
                 "guardrails.md", "pii-policy.md", "cost-latency.md",
                 "failure-taxonomy.md", "model-selection.md"):
        assert (PROJECT_ROOT / "docs" / name).exists(), f"docs/{name} is missing"

    assert (PROJECT_ROOT / "specs" / "acceptance-criteria.md").exists()
