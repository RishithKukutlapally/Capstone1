import time

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from .config import get_config
from .llm import build_structured_llm
from .logging_utils import get_logger, log_interaction
from .query_transform import queries_for_retrieval, transform_query
from .retrieval import retrieve
from .schemas import AnswerStatus, AssistantResponse, GroundedAnswer, RetrievedChunk

logger = get_logger("catalog_rag.generation")

SYSTEM_PROMPT = """You are a catalog and product-compliance assistant for an
e-commerce marketplace. Answer using ONLY the policy clauses given below.

RULES:

1. GROUND EVERYTHING. Every statement must come from the context. You have
   extensive knowledge of real regulations. Do not use it.

2. CITE CLAUSES, NOT DOCUMENTS. Every citation names the exact clause id, for
   example SAF-003-C7, not just SAF-003. Copy ids exactly. Never invent one.

3. ABSTAIN WHEN THE CONTEXT IS INSUFFICIENT. If the clauses do not answer the
   question, set status to "abstained", leave citations empty, and set
   grounding_confidence below 0.3. Abstaining is a correct answer.

4. STATE REQUIREMENTS, DO NOT RULE ON THEM. Never say a product or listing "is
   compliant", "is legal", or "is illegal". When asked whether something is
   allowed, answer by stating what the guidelines require or prohibit, and cite
   the clause. That is an answer, not a determination, so do not abstain merely
   because the question is phrased as "is this allowed?".

5. USE "partial" HONESTLY. If the context answers part of a multi-part question,
   set status to "partial", answer what you can, and say which part is not
   covered. Do not abstain on a multi-part question you can partly answer.

6. GROUNDING CONFIDENCE. Report how well the cited clauses support your answer:
   0.9+ when a clause states it directly, 0.5-0.7 when you combined clauses,
   below 0.3 when support is weak.

FIELDS:
- answer: the answer, in plain language for a catalog operations analyst
- applicable_guideline: which guideline governs this, with its clause id
- requirement: what the seller must do, phrased as an obligation
- labeling_safety_condition: any labeling or safety condition, or "None"
- citations: every clause used, with a short verbatim quote
- reasoning: one sentence on whether the clauses support your answer"""

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "POLICY CLAUSES:\n\n{context}\n\nQUESTION: {question}"),
])

def format_context(docs):
    blocks = []
    for i, doc in enumerate(docs, 1):
        m = doc.metadata
        blocks.append(
            f"[{i}] CLAUSE {m['clause_id']} | DOCUMENT {m['doc_id']} - {m['doc_title']}\n"
            f"SECTION: {m.get('section', '')}\n"
            f"TITLE: {m.get('clause_title', '')}\n\n"
            f"{doc.page_content}"
        )
    return "\n\n---\n\n".join(blocks)

def make_abstention(reason):
    return GroundedAnswer(
        answer=get_config().grounding.abstention_message,
        status=AnswerStatus.ABSTAINED,
        grounding_confidence=0.0,
        reasoning=reason,
    )

def make_error(reason):
    return GroundedAnswer(
        answer=(
            "The assistant could not complete this request because the model provider "
            "could not be reached. This is a system error, not a statement about what "
            "the corpus contains. Please try again."
        ),
        status=AnswerStatus.ERROR,
        grounding_confidence=0.0,
        reasoning=reason,
    )

def check_grounding(answer, docs):
    cfg = get_config()

    if answer.abstained:

        return make_abstention(answer.reasoning or "The model reported the corpus cannot answer.")

    if cfg.grounding.require_citations and len(answer.citations) < cfg.grounding.min_citations:
        logger.warning("Answer had %d citations, abstaining", len(answer.citations))
        return make_abstention("Answer did not carry the required clause-level citation.")

    retrieved = {d.metadata["clause_id"] for d in docs}
    invented = [c.clause_id for c in answer.citations if c.clause_id not in retrieved]
    if invented:
        logger.warning("Model cited clauses that were not retrieved: %s", invented)
        answer.citations = [c for c in answer.citations if c.clause_id in retrieved]
        if not answer.citations:
            return make_abstention(f"All cited clauses were invented: {invented}")

    if answer.grounding_confidence < cfg.grounding.abstention_threshold:
        logger.info("Confidence %.2f below threshold", answer.grounding_confidence)
        return make_abstention(f"Confidence {answer.grounding_confidence:.2f} below threshold.")

    return answer

def answer_question(question, model_name=None):
    cfg = get_config()
    started = time.time()
    model_name = model_name or cfg.llm.primary_model

    transformed = transform_query(question)
    docs = retrieve(transformed.rewritten_query, extra_queries=queries_for_retrieval(transformed))

    if len(docs) < cfg.grounding.min_supporting_chunks:
        logger.info("Nothing survived reranking, abstaining without an LLM call")
        answer = make_abstention("No corpus clause scored above the relevance threshold.")
    else:
        try:
            chain = PROMPT | build_structured_llm(GroundedAnswer, model_name)
            answer = chain.invoke({"context": format_context(docs), "question": question})
            answer = check_grounding(answer, docs)
        except Exception as exc:
            logger.error("Generation failed: %s: %s", type(exc).__name__, exc)
            answer = make_error(f"{type(exc).__name__}: {exc}")

    response = AssistantResponse(
        question=question,
        rewritten_query=transformed.rewritten_query,
        sub_queries=transformed.sub_queries,
        answer=answer,
        retrieved=[
            RetrievedChunk(
                citation=d.metadata["citation"],
                clause_id=d.metadata["clause_id"],
                clause_title=d.metadata.get("clause_title", ""),
                doc_type=d.metadata.get("doc_type", ""),
                text=d.page_content,
                rrf_score=d.metadata.get("rrf_score", 0.0),
                rerank_score=d.metadata.get("rerank_score"),
            )
            for d in docs
        ],
        model=model_name,
        latency_seconds=round(time.time() - started, 3),
    )

    log_interaction(
        question=question,
        answer=answer.answer,
        citations=answer.citation_labels,
        abstained=answer.abstained,
        confidence=answer.grounding_confidence,
        model=model_name,
    )
    return response
