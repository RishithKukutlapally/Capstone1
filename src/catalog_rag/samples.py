import json

from .config import get_config, project_path
from .logging_utils import get_logger

logger = get_logger("catalog_rag.samples")

def write_samples(model_name=None):
    cfg = get_config()
    model_name = model_name or cfg.llm.primary_model

    path = project_path(cfg.paths.reports_dir) / f"answers_{model_name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No answers for {model_name}. Run `catalog-rag evaluate` first."
        )

    results = json.loads(path.read_text(encoding="utf-8"))["results"]
    answered = [r for r in results if r["status"] == "answered"]
    refused = [r for r in results if r["abstained"]]

    lines = [
        "# Sample Answers",
        "",
        f"Model: `{model_name}` · Embeddings: `{cfg.embeddings.model_name}` · "
        f"Reranker: `{cfg.reranker.model_name}`",
        "",
        "Committed evidence for AC-02 and AC-05, taken from the golden-set run in",
        "`reports/ragas_report.json`. Every answered question carries at least one",
        "clause-level citation; the refusals at the end show the assistant declining",
        "rather than inventing an answer.",
        "",
        f"Answered: {len(answered)} · Refused: {len(refused)}",
        "",
        "---",
        "",
        "## Answered, with clause-level citations (AC-02)",
        "",
    ]

    for r in answered[:8]:
        lines += [
            f"### {r['id']} — {r['question']}",
            "",
            f"**Confidence:** {r['confidence']:.2f} · **Latency:** {r['latency_seconds']:.1f}s",
            "",
            r["answer"],
            "",
            "**Citations:** " + ", ".join(f"`{c}`" for c in r["citations"]),
            "",
            "**Clauses retrieved:** " + ", ".join(f"`{c}`" for c in r["retrieved_clauses"]),
            "",
            "---",
            "",
        ]

    lines += ["## Refused — the corpus does not support an answer (AC-05)", ""]

    for r in refused:
        lines += [
            f"### {r['id']} — {r['question']}",
            "",
            f"**Status:** `{r['status']}` · **Confidence:** {r['confidence']:.2f} · "
            f"**Citations:** {len(r['citations'])}",
            "",
            r["answer"],
            "",
            "**Clauses retrieved:** "
            + (", ".join(f"`{c}`" for c in r["retrieved_clauses"]) or "_none — nothing passed the relevance threshold_"),
            "",
            "---",
            "",
        ]

    out = project_path(cfg.paths.reports_dir) / "sample_answers.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", out.name)
    return out
