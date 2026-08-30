import json
import time
from datetime import datetime

import pandas

from . import ragas_compat  # noqa: F401
from langchain_google_genai import ChatGoogleGenerativeAI
from ragas import EvaluationDataset, SingleTurnSample, evaluate as ragas_evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    Faithfulness,
    LLMContextPrecisionWithReference,
    LLMContextRecall,
    ResponseRelevancy,
)
from ragas.run_config import RunConfig

from .config import get_api_key, get_config, project_path
from .embeddings import LocalEmbeddings
from .generation import answer_question
from .llm import check_quota
from .logging_utils import get_logger

logger = get_logger("catalog_rag.evaluate")


def load_golden_set():
    path = project_path(get_config().paths.golden_set_path)
    return json.loads(path.read_text(encoding="utf-8"))["questions"]


def answers_file(model_name):
    return project_path(get_config().paths.reports_dir) / f"answers_{model_name}.json"


# a requirement may be "A|B", meaning either clause satisfies it
def matched(requirement, retrieved):
    return bool(set(requirement.split("|")) & retrieved)


def run_golden_set(model_name):
    cfg = get_config()

    ok, message = check_quota(model_name)
    if not ok:
        raise RuntimeError(f"Cannot start the evaluation. {message}")

    path = answers_file(model_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    done = {}
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))["results"]
        done = {r["id"]: r for r in saved if not r["errored"]}

    results = []
    golden = load_golden_set()

    for i, item in enumerate(golden, 1):
        if item["id"] in done:
            results.append(done[item["id"]])
            continue

        logger.info("[%s] %d/%d %s", model_name, i, len(golden), item["id"])
        response = answer_question(item["question"], model_name=model_name)

        answer = response.answer

        results.append({
            "id": item["id"],
            "question": item["question"],
            "reference_answer": item["reference_answer"],
            "expected_clauses": item["expected_clauses"],
            "acceptance_criteria": item["acceptance_criteria"],
            "question_type": item["question_type"],
            "expect_abstention": item.get("expect_abstention", False),
            "answer": answer.answer,
            "status": answer.status.value,
            "abstained": answer.abstained,
            "errored": answer.errored,
            "confidence": answer.grounding_confidence,
            "citations": answer.citation_labels,
            "retrieved_clauses": [c.clause_id for c in response.retrieved],
            "retrieved_texts": [c.text for c in response.retrieved],
            "latency_seconds": response.latency_seconds,
        })

        path.write_text(
            json.dumps({"model": model_name, "results": results}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        time.sleep(cfg.eval.request_delay_seconds)

    return results


def score_deterministic(results):
    errored = [r for r in results if r["errored"]]
    usable = [r for r in results if not r["errored"]]
    answerable = [r for r in usable if not r["expect_abstention"]]
    out_of_corpus = [r for r in usable if r["expect_abstention"]]

    expected_count = 0
    found_count = 0
    for result in answerable:
        retrieved = set(result["retrieved_clauses"])
        for requirement in result["expected_clauses"]:
            expected_count += 1
            if matched(requirement, retrieved):
                found_count += 1

    refused = 0
    for result in out_of_corpus:
        if result["abstained"]:
            refused += 1

    answered = [r for r in answerable if not r["abstained"]]
    cited = 0
    for result in answered:
        if result["citations"]:
            cited += 1

    if expected_count:
        recall = round(found_count / expected_count, 4)
    else:
        recall = 0.0

    return {
        "pipeline_errors": len(errored),
        "questions_scored": len(usable),
        "retrieval_recall": recall,
        "clauses_found": f"{found_count}/{expected_count}",
        "abstention_accuracy": round(refused / len(out_of_corpus), 4) if out_of_corpus else 0.0,
        "correct_abstentions": f"{refused}/{len(out_of_corpus)}",
        "false_abstentions": sum(1 for r in answerable if r["abstained"]),
        "citation_rate": round(cited / len(answered), 4) if answered else 0.0,
        "answers_with_citation": f"{cited}/{len(answered)}",
        "mean_latency_seconds": round(
            sum(r["latency_seconds"] for r in usable) / len(usable), 2) if usable else 0.0,
    }


def score_ragas(results):
    cfg = get_config()
    scorable = [r for r in results
                if not r["expect_abstention"] and r["retrieved_texts"] and not r["errored"]]
    if not scorable:
        raise RuntimeError("Nothing to score.")

    dataset = EvaluationDataset(samples=[
        SingleTurnSample(
            user_input=r["question"],
            retrieved_contexts=r["retrieved_texts"],
            response=r["answer"],
            reference=r["reference_answer"],
        )
        for r in scorable
    ])

    judge = LangchainLLMWrapper(ChatGoogleGenerativeAI(
        model=cfg.eval.judge_model,
        temperature=cfg.eval.judge_temperature,
        google_api_key=get_api_key(),
    ))

    logger.info("Scoring %d samples with %s", len(scorable), cfg.eval.judge_model)

    scores = ragas_evaluate(
        dataset=dataset,
        metrics=[
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
            Faithfulness(),
            # strictness=1 asks for one question per call; the default of 3
            # makes Gemini reject the request with "multiple candidates"
            ResponseRelevancy(strictness=1),
        ],
        llm=judge,
        embeddings=LangchainEmbeddingsWrapper(LocalEmbeddings(cfg.embeddings)),
        # ragas defaults to 180s, too short for a thinking model
        run_config=RunConfig(timeout=cfg.eval.judge_timeout_seconds,
                             max_workers=cfg.eval.judge_workers),
    )

    frame = scores.to_pandas()
    metric_columns = [c for c in frame.columns if frame[c].dtype.kind in "fi"]

    output = {}
    for column in metric_columns:
        values = frame[column].dropna()
        if len(values):
            output[column] = round(float(values.mean()), 4)
        else:
            logger.error("Metric %s failed on every sample", column)

    if not output:
        raise RuntimeError("RAGAS produced no values. Check the API key and quota.")

    for position, result in enumerate(scorable):
        row = frame.iloc[position]
        scores_for_this_question = {}
        for column in metric_columns:
            value = row[column]
            if pandas.isna(value):
                scores_for_this_question[column] = None
            else:
                scores_for_this_question[column] = round(float(value), 4)
        result["ragas_scores"] = scores_for_this_question

    output["samples_scored"] = len(scorable)
    return output


def table(rows, headers):
    lines = ["| " + " | ".join(headers) + " |", "|---" * len(headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return lines


def write_report(results, ragas, deterministic, model_name):
    cfg = get_config()
    reports = project_path(cfg.paths.reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")

    (reports / "ragas_report.json").write_text(json.dumps({
        "generated_at": generated,
        "business_case_id": "AAIE_021_ECM",
        "generator_model": model_name,
        "judge_model": cfg.eval.judge_model,
        "embedding_model": cfg.embeddings.model_name,
        "reranker_model": cfg.reranker.model_name,
        "questions_total": len(results),
        "ragas_metrics": ragas,
        "deterministic_metrics": deterministic,
        "retrieval_config": {
            "bm25_top_k": cfg.retrieval.bm25_top_k,
            "vector_top_k": cfg.retrieval.vector_top_k,
            "rrf_k": cfg.retrieval.rrf_k,
            "fusion_top_k": cfg.retrieval.fusion_top_k,
            "final_top_k": cfg.retrieval.final_top_k,
            "rerank_threshold": cfg.reranker.score_threshold,
            "abstention_threshold": cfg.grounding.abstention_threshold,
        },
        "per_question": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    def score_of(result, name):
        value = (result.get("ragas_scores") or {}).get(name)
        return "-" if value is None else value

    per_question = []
    for r in results:
        retrieved = set(r["retrieved_clauses"])
        hits = sum(1 for req in r["expected_clauses"] if matched(req, retrieved))
        found = f"{hits}/{len(r['expected_clauses'])}" if r["expected_clauses"] else "n/a"
        per_question.append([
            r["id"], r["question_type"], r["status"], found, len(r["citations"]),
            score_of(r, "llm_context_precision_with_reference"),
            score_of(r, "context_recall"),
            score_of(r, "faithfulness"),
            score_of(r, "answer_relevancy"),
        ])

    lines = [
        "# RAGAS Evaluation Report", "",
        f"Generated: {generated}  ",
        f"Generator: `{model_name}` · Judge: `{cfg.eval.judge_model}` · "
        f"Embeddings: `{cfg.embeddings.model_name}` · Reranker: `{cfg.reranker.model_name}`", "",
        "## RAGAS metrics (AC-09)", "",
        *table([[k, v] for k, v in ragas.items()], ["Metric", "Score"]), "",
        "Abstention questions are excluded: a correct abstention has no retrieved",
        "context by design. They are measured below.", "",
        "## Deterministic metrics", "",
        *table([[k, v] for k, v in deterministic.items()], ["Metric", "Value"]), "",
        "## Per-question results", "",
        "A dash means the question was excluded from RAGAS scoring: abstention",
        "questions have no retrieved context to score against.", "",
        *table(per_question, ["ID", "Type", "Status", "Expected found", "Citations",
                              "Context precision", "Context recall",
                              "Faithfulness", "Answer relevancy"]),
    ]
    (reports / "ragas_report.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote reports/ragas_report.json and .md")


def run_evaluation(model_name=None):
    model_name = model_name or get_config().llm.primary_model
    results = run_golden_set(model_name)
    deterministic = score_deterministic(results)
    ragas = score_ragas(results)
    write_report(results, ragas, deterministic, model_name)
    return {"ragas": ragas, "deterministic": deterministic}


def compare_models():
    cfg = get_config()
    reports = project_path(cfg.paths.reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")

    comparison = {}
    for model_name in cfg.eval.comparison_models:
        results = run_golden_set(model_name)
        comparison[model_name] = {
            "ragas": score_ragas(results),
            "deterministic": score_deterministic(results),
        }

    (reports / "model_comparison.json").write_text(json.dumps({
        "generated_at": generated,
        "judge_model": cfg.eval.judge_model,
        "note": "Retrieval, prompts and dataset are identical across models; "
                "only the generator changes.",
        "models": comparison,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    models = list(comparison)

    metric_names = []
    for model in models:
        for name in comparison[model]["ragas"]:
            if name not in metric_names:
                metric_names.append(name)
        for name in comparison[model]["deterministic"]:
            if name not in metric_names:
                metric_names.append(name)

    rows = []
    for name in metric_names:
        row = [name]
        for model in models:
            scores = comparison[model]
            if name in scores["ragas"]:
                row.append(scores["ragas"][name])
            elif name in scores["deterministic"]:
                row.append(scores["deterministic"][name])
            else:
                row.append("-")
        rows.append(row)

    lines = [
        "# Two-Model Comparison (AC-10)", "",
        f"Generated: {generated}", "",
        "Both models answered the same golden set with identical retrieval, reranking",
        "and prompts. Only the generator changed.", "",
        *table(rows, ["Metric"] + [f"`{m}`" for m in models]), "",
        "Selection rationale: see docs/model-selection.md",
    ]
    (reports / "model_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote reports/model_comparison.json and .md")
    return comparison
