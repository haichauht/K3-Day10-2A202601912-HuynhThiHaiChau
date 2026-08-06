from __future__ import annotations

import json
import math

from core.config import load_settings
from core.utils import file_sha256, read_json


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    required = {
        "raw response": paths.raw_api_response,
        "raw records": paths.raw_records_json,
        "baseline clean": paths.clean_json,
        "corrupted clean": paths.corrupted_clean_json,
        "repaired clean": paths.repaired_clean_json,
        "test set": paths.eval_testset,
        "baseline metrics": paths.baseline_metrics,
        "corrupted metrics": paths.corrupted_metrics,
        "repaired metrics": paths.repaired_metrics,
        "corruption log": paths.corruption_log,
        "baseline report": paths.baseline_report,
        "comparison report": paths.comparison_report,
        "C5 group report": paths.project_dir / "report" / "group_report.md",
        "C5 individual report": paths.project_dir / "report" / "individual_2A202601912.md",
    }
    errors = [f"Missing {label}: {path}" for label, path in required.items() if not path.exists()]
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, indent=2))
        raise SystemExit(1)

    comparison_path = paths.corruption_log.parent / "comparison_metrics.json"
    comparison = read_json(comparison_path)
    actual_hash = file_sha256(paths.eval_testset)
    if comparison.get("test_set_sha256") != actual_hash:
        errors.append("Test-set SHA-256 differs from comparison_metrics.json.")

    metric_paths = {
        "baseline": paths.baseline_metrics,
        "corrupted": paths.corrupted_metrics,
        "repaired": paths.repaired_metrics,
    }
    required_ragas_metrics = (
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "faithfulness",
    )
    ragas_models: set[str] = set()
    for state, path in metric_paths.items():
        metrics = read_json(path)
        if metrics != comparison.get(state, {}).get("metrics"):
            errors.append(f"{state} metrics differ from comparison_metrics.json.")
        if metrics.get("judge_fallback_rate") != 0:
            errors.append(f"{state} evaluation used judge fallback.")
        ragas = metrics.get("ragas", {})
        if ragas.get("model"):
            ragas_models.add(str(ragas["model"]))
        for name in required_ragas_metrics:
            value = ragas.get(name)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                errors.append(f"{state} Ragas metric is missing or invalid: {name}.")

    manifests = [
        read_json(paths.embeddings_json),
        read_json(paths.corrupted_embeddings_json),
        read_json(paths.repaired_embeddings_json),
    ]
    collection_names = [manifest.get("collection_name") for manifest in manifests]
    if len(set(collection_names)) != 3:
        errors.append(f"Collections are not distinct: {collection_names}")

    baseline = read_json(paths.clean_json)
    corrupted = read_json(paths.corrupted_clean_json)
    repaired = read_json(paths.repaired_clean_json)
    baseline_ids = [item["paper_id"] for item in baseline]
    repaired_ids = [item["paper_id"] for item in repaired]
    if baseline_ids != repaired_ids:
        errors.append("Repaired document lineage does not match baseline lineage.")
    if len(corrupted) >= len(baseline):
        errors.append("Corrupted dataset did not reduce net row count as expected.")
    for manifest, records, state in zip(
        manifests, (baseline, corrupted, repaired), ("baseline", "corrupted", "repaired"), strict=True
    ):
        if manifest.get("document_count") != len(records):
            errors.append(f"{state} embedding manifest count does not match cleaned records.")

    quality_expectations = {"baseline": True, "corrupted": False, "repaired": True}
    for state, expected in quality_expectations.items():
        quality = read_json(paths.quality_dir / f"{state}_quality_report.json")
        if quality.get("overall_success") is not expected:
            errors.append(f"Unexpected {state} quality status.")

    agent_demo = read_json(paths.demo_answers)
    if agent_demo.get("backend") != "langchain_agent" or not agent_demo.get("answers"):
        errors.append("Agent demo did not complete with the LangChain agent backend.")

    result = {
        "status": "passed" if not errors else "failed",
        "test_set_sha256": actual_hash,
        "collections": collection_names,
        "row_counts": {
            "baseline": len(baseline),
            "corrupted": len(corrupted),
            "repaired": len(repaired),
        },
        "agent_backend": agent_demo.get("backend"),
        "ragas_models": sorted(ragas_models),
        "errors": errors,
    }
    print(json.dumps(result, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
