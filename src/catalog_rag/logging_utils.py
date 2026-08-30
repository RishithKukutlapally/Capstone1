from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from .config import get_config, project_path

PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\b(?:ORD|ORDER|SO)[-_]?\d{4,}\b", re.I), "[ORDER_ID]"),
    (re.compile(r"\bSELLER[-_]?[A-Z0-9]{4,}\b", re.I), "[SELLER_ID]"),
    (re.compile(r"\+?\d[\d\s-]{8,}\d"), "[PHONE]"),
]

def mask_pii(text: str) -> str:
    for pattern, placeholder in PII_PATTERNS:
        text = pattern.sub(placeholder, text or "")
    return text

def get_logger(name: str = "catalog_rag") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logging.getLogger("catalog_rag").handlers:
        cfg = get_config()
        root = logging.getLogger("catalog_rag")
        root.setLevel(cfg.logging.level)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
        root.addHandler(handler)
    return logger

def log_interaction(question, answer, citations, abstained, confidence, model):
    cfg = get_config()
    if not cfg.logging.log_queries:
        return

    log_dir = project_path(cfg.paths.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "question": mask_pii(question) if cfg.logging.mask_pii else question,
        "answer": mask_pii(answer) if cfg.logging.mask_pii else answer,
        "citations": citations,
        "abstained": abstained,
        "confidence": confidence,
    }
    with (log_dir / "interactions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
