import argparse
import json

def cmd_ingest(args):
    from .ingest import ingest

    summary = ingest(rebuild=args.rebuild)
    print(json.dumps(summary, indent=2))
    if summary["vectors_before"] == summary["vectors_after"] and summary["vectors_before"]:
        print("Idempotent: the second run added no new vectors (AC-01).")

def cmd_ask(args):
    from .generation import answer_question

    response = answer_question(args.question, model_name=args.model)
    answer = response.answer

    print(f"\n[{answer.status.value.upper()}]  confidence {answer.grounding_confidence:.2f}  "
          f"{response.latency_seconds:.1f}s  {response.model}\n")
    print(answer.answer)

    if answer.status.value == "answered":
        print(f"\nApplicable guideline : {answer.applicable_guideline}")
        print(f"Requirement          : {answer.requirement}")
        print(f"Labeling / safety    : {answer.labeling_safety_condition}")

    if answer.citations:
        print("\nCitations:")
        for c in answer.citations:
            print(f"  {c.clause_id}  {c.doc_title or c.doc_id}")

    if args.show_context:
        print("\nRetrieved clauses (after reranking):")
        for chunk in response.retrieved:
            print(f"  {chunk.clause_id:14s} rerank={chunk.rerank_score}  {chunk.clause_title}")

def cmd_search(args):
    from .retrieval import retrieve

    for doc in retrieve(args.query):
        m = doc.metadata
        print(f"  {m['clause_id']:14s} rerank={m.get('rerank_score')}  {m['clause_title']}")

def cmd_evaluate(args):
    from .evaluate import run_evaluation

    scores = run_evaluation(model_name=args.model)
    print(json.dumps(scores, indent=2))
    print("\nWrote reports/ragas_report.json and reports/ragas_report.md")

def cmd_compare(args):
    from .evaluate import compare_models

    compare_models()
    print("\nWrote reports/model_comparison.json and reports/model_comparison.md")

def cmd_samples(args):
    from .samples import write_samples

    print(f"Wrote {write_samples(args.model)}")

def cmd_all(args):
    from .evaluate import compare_models, run_evaluation
    from .ingest import ingest
    from .samples import write_samples

    print("1/4 ingesting");  ingest()
    print("2/4 evaluating"); run_evaluation()
    print("3/4 comparing");  compare_models()
    print("4/4 samples");    write_samples()
    print("\nDone. All artifacts are in reports/")

def app():
    parser = argparse.ArgumentParser(prog="catalog-rag", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="build the index from the corpus")
    p.add_argument("--rebuild", action="store_true", help="delete the index and start over")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("ask", help="ask one question")
    p.add_argument("question")
    p.add_argument("--model", default=None, help="override the Gemini model")
    p.add_argument("--show-context", action="store_true", help="also print retrieved clauses")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("search", help="show retrieval only, no LLM call")
    p.add_argument("query")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("evaluate", help="golden set + RAGAS -> reports/")
    p.add_argument("--model", default=None)
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("compare", help="compare the candidate models")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("samples", help="write reports/sample_answers.md (no API calls)")
    p.add_argument("--model", default=None)
    p.set_defaults(func=cmd_samples)

    p = sub.add_parser("all", help="ingest + evaluate + compare + samples")
    p.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    app()
