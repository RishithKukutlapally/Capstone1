from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .config import get_config
from .llm import build_structured_llm
from .logging_utils import get_logger

logger = get_logger("catalog_rag.query_transform")

class TransformedQuery(BaseModel):
    rewritten_query: str = Field(description="The question in policy vocabulary")
    sub_queries: list[str] = Field(default_factory=list, description="Independent sub-questions, empty if single-part")
    expansion_terms: list[str] = Field(default_factory=list, description="Domain synonyms to help keyword search")

PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     """You rewrite questions for a search engine over e-commerce catalog and
product-compliance policy documents.

The corpus covers listing standards, category guidelines, product safety and
labeling, restricted substances, and image and content guidelines.

Do three things:

1. rewritten_query: restate the question in the formal vocabulary of policy
   documents - "shall", "requirement", "labelling", "prohibited",
   "concentration limit". Keep the meaning exactly. Do not answer it.

2. sub_queries: if the question asks about more than one thing, split it into at
   most {max_sub_queries} standalone questions. Otherwise return an empty list.

3. expansion_terms: 3-6 synonyms or related domain terms a relevant clause would
   likely contain.

Never invent product names or regulations. You are rewriting, not answering."""),
    ("human", "{question}"),
])

def transform_query(question):
    cfg = get_config()

    if not cfg.query_transform.enabled:
        return TransformedQuery(rewritten_query=question)

    if len(question) < cfg.query_transform.min_chars_for_decomposition:
        return TransformedQuery(rewritten_query=question)

    try:
        chain = PROMPT | build_structured_llm(TransformedQuery)
        result = chain.invoke({
            "question": question,
            "max_sub_queries": cfg.query_transform.max_sub_queries,
        })
    except Exception as exc:
        logger.warning("Query transformation failed (%s), using the original question", exc)
        return TransformedQuery(rewritten_query=question)

    result.sub_queries = result.sub_queries[:cfg.query_transform.max_sub_queries]
    logger.info("Rewrote to '%s' with %d sub-queries", result.rewritten_query, len(result.sub_queries))
    return result

def queries_for_retrieval(transformed):
    queries = [transformed.rewritten_query]

    if transformed.expansion_terms:
        queries.append(transformed.rewritten_query + " " + " ".join(transformed.expansion_terms))

    queries.extend(transformed.sub_queries)
    return queries
