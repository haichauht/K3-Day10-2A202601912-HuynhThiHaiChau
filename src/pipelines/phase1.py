from __future__ import annotations

from datetime import UTC, datetime
import json

from core.config import load_settings
from core.utils import dataframe_records, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def _load_or_fetch_records(settings):
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        return fetch_source_records(settings), "fetched"
    return load_raw_records(settings.paths.raw_records_json), "snapshot"


def _load_or_build_test_set(df, settings) -> list[dict]:
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        return build_test_set(df, settings.paths.eval_testset)

    test_set = read_json(settings.paths.eval_testset)
    valid_ids = set(df["paper_id"].astype(str))
    if (
        not isinstance(test_set, list)
        or not test_set
        or any(not set(item.get("ground_truth_doc_ids", [])) <= valid_ids for item in test_set)
    ):
        return build_test_set(df, settings.paths.eval_testset)
    return test_set


def _write_agent_demo(settings, index: LocalEmbeddingIndex, test_set: list[dict]) -> None:
    questions = [item["question"] for item in test_set[:3]]
    payload: dict[str, object] = {"backend": "langchain_agent", "answers": []}
    try:
        agent = build_agent(settings, index)
        payload["answers"] = [
            {"question": question, "answer": run_agent_question(agent, question)} for question in questions
        ]
    except Exception as exc:
        # The core pipeline remains reproducible without a paid LLM credential.
        payload["backend"] = "deterministic_retrieval_qa_fallback"
        payload["fallback_reason"] = f"{type(exc).__name__}: {exc}"
        payload["answers"] = []
        for question in questions:
            result = answer_question(question, settings=settings, index=index)
            payload["answers"].append(
                {
                    "question": question,
                    "answer": result.answer,
                    "retrieved_doc_ids": result.retrieved_doc_ids,
                    "retrieved_titles": result.retrieved_titles,
                }
            )
    write_json(settings.paths.demo_answers, payload)


def main() -> None:
    """Run raw → clean → index → evaluate → observe → report for baseline data."""
    settings = load_settings()
    records, source_mode = _load_or_fetch_records(settings)
    clean_df = build_clean_dataframe(records, run_date=datetime.now(UTC))
    cleaning_summary = dict(clean_df.attrs.get("cleaning_summary", {}))
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, dataframe_records(clean_df))

    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    test_set = _load_or_build_test_set(clean_df, settings)
    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    _write_agent_demo(settings, index, test_set)

    source_summary = {
        "source": settings.source_api,
        "source_mode": source_mode,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "requested_records": settings.max_results,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "cleaning": cleaning_summary,
        "raw_response_artifact": str(settings.paths.raw_api_response),
        "raw_records_artifact": str(settings.paths.raw_records_json),
        "collection": index.collection_name,
        "evaluation_samples": len(test_set),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        freshness,
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "clean_records": len(clean_df),
                "evaluation_samples": len(test_set),
                "metrics": evaluation.summary,
                "quality_success": quality["overall_success"],
                "freshness_status": freshness["status"],
                "report": str(settings.paths.baseline_report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
