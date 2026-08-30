import json
import re

from langchain_chroma import Chroma
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from .config import get_config, project_path
from .embeddings import LocalEmbeddings
from .logging_utils import get_logger

logger = get_logger("catalog_rag.retrieval")

_store = None
_bm25 = None
_reranker = None

CLAUSE_ID = r"[a-z]{3}-\d{3}(?:-c\d{1,2})?"

def tokenize(text):
    text = text.lower()
    ids = re.findall(CLAUSE_ID, text)
    words = re.findall(r"[a-z0-9]+", re.sub(CLAUSE_ID, " ", text))
    return ids + words

def load_chunks():
    path = project_path(get_config().paths.bm25_index_path)
    if not path.exists():
        raise FileNotFoundError("No index found. Run `catalog-rag ingest` first.")
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [Document(id=r["id"], page_content=r["text"], metadata=r["metadata"]) for r in rows]

def get_store():
    global _store
    if _store is None:
        cfg = get_config()
        _store = Chroma(
            collection_name=cfg.vector_store.collection_name,
            embedding_function=LocalEmbeddings(cfg.embeddings),
            persist_directory=str(project_path(cfg.paths.vector_store_dir)),
        )
    return _store

def get_bm25():
    global _bm25
    if _bm25 is None:
        cfg = get_config()
        chunks = load_chunks()
        _bm25 = BM25Retriever.from_documents(
            chunks, k=cfg.retrieval.bm25_top_k, preprocess_func=tokenize
        )
        logger.info("BM25 index ready over %d chunks", len(chunks))
    return _bm25

def get_reranker():
    global _reranker
    if _reranker is None:
        cfg = get_config()
        logger.info("Loading reranker %s", cfg.reranker.model_name)
        _reranker = HuggingFaceCrossEncoder(model_name=cfg.reranker.model_name)
    return _reranker

def fuse_with_rrf(result_lists):
    cfg = get_config()
    scores = {}
    seen = {}

    for results in result_lists:
        for position, doc in enumerate(results):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (cfg.retrieval.rrf_k + position + 1)
            seen[doc.id] = doc

    ranked = sorted(scores, key=scores.get, reverse=True)

    fused = []
    for chunk_id in ranked[:cfg.retrieval.fusion_top_k]:
        doc = seen[chunk_id]
        doc.metadata["rrf_score"] = round(scores[chunk_id], 6)
        fused.append(doc)
    return fused

def rerank(question, docs):
    cfg = get_config()
    if not cfg.reranker.enabled or not docs:
        return docs[:cfg.retrieval.final_top_k]

    scores = get_reranker().score([(question, doc.page_content) for doc in docs])
    for doc, score in zip(docs, scores):
        doc.metadata["rerank_score"] = round(float(score), 4)

    keep = [d for d in docs if d.metadata["rerank_score"] >= cfg.reranker.score_threshold]
    keep.sort(key=lambda d: d.metadata["rerank_score"], reverse=True)

    if len(keep) < len(docs):
        logger.info("Reranker dropped %d weak chunks of %d", len(docs) - len(keep), len(docs))

    return keep[:cfg.retrieval.final_top_k]

def retrieve(question, extra_queries=None):
    cfg = get_config()
    questions = extra_queries or [question]

    result_lists = []
    for q in questions:
        result_lists.append(get_bm25().invoke(q))
        result_lists.append(get_store().similarity_search(q, k=cfg.retrieval.vector_top_k))

    final = rerank(question, fuse_with_rrf(result_lists))
    logger.info("Found: %s", [d.metadata["clause_id"] for d in final])
    return final
