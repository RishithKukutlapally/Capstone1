import hashlib
import json
import re

import yaml
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import get_config, project_path
from .embeddings import LocalEmbeddings
from .logging_utils import get_logger

logger = get_logger("catalog_rag.ingest")

CLAUSE_HEADING = re.compile(r"^###\s+([A-Z]{3}-\d{3}-C\d{1,2})\s+(.+)$")
SECTION_HEADING = re.compile(r"^##\s+(.+)$")


def parse_document(path):
    lines = path.read_text(encoding="utf-8").splitlines()

    frontmatter = []
    body_start = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                body_start = i + 1
                break
            frontmatter.append(line)

    meta = yaml.safe_load("\n".join(frontmatter)) or {}
    clauses = []
    section = "General"
    current = None

    for line in lines[body_start:]:
        clause = CLAUSE_HEADING.match(line)
        heading = SECTION_HEADING.match(line)

        if clause:
            current = {"clause_id": clause.group(1),
                       "clause_title": clause.group(2).strip(),
                       "section": section,
                       "lines": []}
            clauses.append(current)
        elif heading:
            section = heading.group(1).strip()
            current = None
        elif current:
            current["lines"].append(line)

    for clause in clauses:
        clause["text"] = "\n".join(clause.pop("lines")).strip()

    return meta, [c for c in clauses if c["text"]]


def make_chunks():
    cfg = get_config()
    files = sorted(project_path(cfg.paths.corpus_dir).glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No documents in {cfg.paths.corpus_dir}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunking.chunk_size,
        chunk_overlap=cfg.chunking.chunk_overlap,
        separators=cfg.chunking.separators,
    )

    chunks = []
    for path in files:
        meta, clauses = parse_document(path)

        for clause in clauses:
            too_long = len(clause["text"]) > cfg.chunking.max_chunk_chars
            parts = splitter.split_text(clause["text"]) if too_long else [clause["text"]]

            for number, part in enumerate(parts):
                breadcrumb = (f"{meta['title']} > {clause['section']} > "
                              f"{clause['clause_id']} {clause['clause_title']}")
                text = f"{breadcrumb}\n\n{part}" if cfg.chunking.prepend_breadcrumb else part
                key = f"{meta['doc_id']}|{clause['clause_id']}|{number}|{part}"
                digest = hashlib.sha1(key.encode()).hexdigest()[:12]

                chunks.append(Document(
                    id=f"{meta['doc_id']}-{clause['clause_id']}-{number}-{digest}",
                    page_content=text,
                    metadata={
                        "doc_id": meta["doc_id"],
                        "doc_title": meta["title"],
                        "doc_type": meta["doc_type"],
                        "category": meta["category"],
                        "section": clause["section"],
                        "clause_id": clause["clause_id"],
                        "clause_title": clause["clause_title"],
                        "source_file": path.name,
                        "citation": f"{meta['doc_id']} {clause['clause_id']}",
                    },
                ))
    return chunks


def open_store():
    cfg = get_config()
    folder = project_path(cfg.paths.vector_store_dir)
    folder.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=cfg.vector_store.collection_name,
        embedding_function=LocalEmbeddings(cfg.embeddings),
        persist_directory=str(folder),
    )


def count_vectors(store):
    return len(store.get(include=[])["ids"])


def ingest(rebuild=False):
    cfg = get_config()
    chunks = make_chunks()
    logger.info("Built %d chunks", len(chunks))

    store = open_store()
    if rebuild:
        store.delete_collection()
        store = open_store()

    before = count_vectors(store)
    batch = cfg.vector_store.upsert_batch_size

    for start in range(0, len(chunks), batch):
        window = chunks[start:start + batch]
        ids = [c.id for c in window]
        # delete then add with the same ids: this is what makes a second
        # ingest a no-op instead of doubling the collection (AC-01)
        store.delete(ids=ids)
        store.add_documents(window, ids=ids)
        logger.info("Stored %d of %d", start + len(window), len(chunks))

    index_file = project_path(cfg.paths.bm25_index_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"id": c.id, "text": c.page_content, "metadata": c.metadata} for c in chunks]
    index_file.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "documents": len({c.metadata["doc_id"] for c in chunks}),
        "chunks": len(chunks),
        "vectors_before": before,
        "vectors_after": count_vectors(store),
        "embedding_model": cfg.embeddings.model_name,
    }
    logger.info("Done: %s", summary)
    return summary
