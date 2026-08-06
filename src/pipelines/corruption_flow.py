from __future__ import annotations

from datetime import UTC, datetime
import json

import pandas as pd

from core.config import load_settings
from core.utils import dataframe_records, file_sha256, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _require_baseline(settings) -> None:
    required = (
        settings.paths.raw_records_json,
        settings.paths.clean_csv,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
        settings.paths.embeddings_json,
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Corruption flow requires a completed baseline. Missing artifacts:\n- " + "\n- ".join(missing)
        )


def _assert_ground_truth_exists(df: pd.DataFrame, test_set: list[dict], state: str) -> None:
    available_ids = set(df["paper_id"].astype(str))
    missing_ids = sorted(
        {
            doc_id
            for item in test_set
            for doc_id in item.get("ground_truth_doc_ids", [])
            if doc_id not in available_ids
        }
    )
    if missing_ids:
        raise RuntimeError(f"{state} data does not contain test-set ground-truth IDs: {missing_ids}")


def main() -> None:
    """Run corrupt → evaluate → repair from raw → evaluate → compare."""
    settings = load_settings()
    _require_baseline(settings)
    baseline_df = pd.read_csv(settings.paths.clean_csv, keep_default_na=False)
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    test_set = read_json(settings.paths.eval_testset)
    test_set_hash_before = file_sha256(settings.paths.eval_testset)

    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, dataframe_records(corrupted_df))
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df, settings, settings.paths.corrupted_embeddings_json
    )
    corrupted_evaluation = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness_path = settings.paths.quality_dir / "corrupted_freshness_report.json"
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, corrupted_freshness_path
    )

    # Repair uses the immutable raw snapshot and the same cleaning contract as baseline.
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date=datetime.now(UTC))
    _assert_ground_truth_exists(repaired_df, test_set, "Repaired")
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, dataframe_records(repaired_df))
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, settings.paths.repaired_embeddings_json
    )
    repaired_evaluation = evaluate_pipeline(
        settings,
        repaired_index,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness_path = settings.paths.quality_dir / "repaired_freshness_report.json"
    repaired_freshness = build_freshness_report(repaired_df, settings, repaired_freshness_path)

    test_set_hash_after = file_sha256(settings.paths.eval_testset)
    if test_set_hash_after != test_set_hash_before:
        raise RuntimeError("Evaluation test set changed during the corruption flow.")

    baseline_quality_path = settings.paths.quality_dir / "baseline_quality_report.json"
    baseline_quality = read_json(baseline_quality_path) if baseline_quality_path.exists() else None
    baseline_freshness = (
        read_json(settings.paths.freshness_report) if settings.paths.freshness_report.exists() else None
    )
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_evaluation.summary,
        repaired_evaluation.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        baseline_quality=baseline_quality,
        baseline_freshness=baseline_freshness,
    )

    comparison_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "test_set_path": str(settings.paths.eval_testset),
        "test_set_sha256": test_set_hash_after,
        "embedding_model": settings.embedding_model,
        "top_k": settings.top_k,
        "baseline": {
            "metrics": baseline_metrics,
            "quality": baseline_quality,
            "freshness": baseline_freshness,
        },
        "corrupted": {
            "metrics": corrupted_evaluation.summary,
            "quality": corrupted_quality,
            "freshness": corrupted_freshness,
        },
        "repaired": {
            "metrics": repaired_evaluation.summary,
            "quality": repaired_quality,
            "freshness": repaired_freshness,
        },
    }
    write_json(settings.paths.corruption_log.parent / "comparison_metrics.json", comparison_payload)
    print(
        json.dumps(
            {
                "status": "completed",
                "test_set_sha256": test_set_hash_after,
                "baseline_metrics": baseline_metrics,
                "corrupted_metrics": corrupted_evaluation.summary,
                "repaired_metrics": repaired_evaluation.summary,
                "report": str(settings.paths.comparison_report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
