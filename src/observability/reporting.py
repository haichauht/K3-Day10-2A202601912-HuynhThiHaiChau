from __future__ import annotations

import json
from typing import Any

from core.utils import write_text


_METRIC_NAMES = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")
_RAGAS_METRIC_NAMES = ("answer_relevancy", "context_precision", "context_recall", "faithfulness")


def _escape(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_metric(value: Any) -> str:
    return f"{value:.4f}" if isinstance(value, (int, float)) else _escape(value)


def _quality_label(quality: dict[str, Any] | None) -> str:
    if not quality:
        return "N/A"
    status = "PASS" if quality.get("overall_success") else "FAIL"
    failed = quality.get("failed_checks") or []
    return status if not failed else f"{status} ({', '.join(map(str, failed))})"


def _freshness_label(freshness: dict[str, Any] | None) -> str:
    if not freshness:
        return "N/A"
    return f"{str(freshness.get('status', 'unknown')).upper()} ({freshness.get('stale_rows', 0)} stale rows)"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a baseline report whose values come directly from generated artifacts."""
    source_rows = "\n".join(f"| `{_escape(key)}` | {_escape(value)} |" for key, value in source_summary.items())
    metric_rows = "\n".join(
        f"| `{name}` | {_format_metric(metrics.get(name, 'N/A'))} |" for name in _METRIC_NAMES
    )
    check_rows = "\n".join(
        f"| `{_escape(item.get('name'))}` | {_escape(item.get('dimension'))} | "
        f"{'PASS' if item.get('success') else 'FAIL'} | {_escape(item.get('observed'))} | "
        f"{_escape(item.get('expectation'))} |"
        for item in quality.get("checks", [])
    )
    ragas = metrics.get("ragas", {"skipped": "No Ragas result recorded."})
    markdown = f"""# Day 10 — Baseline Pipeline Report

This report is generated from the same JSON/CSV artifacts produced by the baseline run.

## Source and lineage

| Field | Value |
| --- | --- |
{source_rows}

## RAG evaluation

| Metric | Value |
| --- | ---: |
{metric_rows}

- Evaluation samples: **{_escape(metrics.get('samples', 0))}**
- Judge backends: `{_escape(metrics.get('judge_backend_counts', {}))}`
- Judge fallback rate: **{_format_metric(metrics.get('judge_fallback_rate', 0.0))}**
- Ragas: `{_escape(ragas)}`

## Data quality

- Overall status: **{_quality_label(quality)}**
- Passed checks: **{quality.get('passed_checks', 0)}/{len(quality.get('checks', []))}**

| Check | Dimension | Result | Observed | Expectation |
| --- | --- | --- | ---: | --- |
{check_rows}

## Freshness

| Signal | Value |
| --- | --- |
| Status | **{_freshness_label(freshness)}** |
| Latest publication | {_escape(freshness.get('latest_published'))} |
| Oldest publication | {_escape(freshness.get('oldest_published'))} |
| Threshold | {freshness.get('freshness_threshold_days')} days |
| Total rows | {freshness.get('total_rows')} |

## Interpretation

The baseline establishes the reference dataset, fixed evaluation set, collection, metrics, and
observability signals. Corrupted and repaired runs must reuse this evaluation set and retrieval
configuration so any measured change can be attributed to the data state rather than evaluator drift.
"""
    write_text(report_path, markdown)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
) -> None:
    """Write a three-state comparison with computed deltas and cautious conclusions."""
    rows: list[str] = []
    for name in _METRIC_NAMES:
        baseline = baseline_metrics.get(name)
        corrupted = corrupted_metrics.get(name)
        repaired = repaired_metrics.get(name)
        corrupt_delta = corrupted - baseline if isinstance(corrupted, (int, float)) and isinstance(baseline, (int, float)) else None
        recovery = repaired - corrupted if isinstance(repaired, (int, float)) and isinstance(corrupted, (int, float)) else None
        rows.append(
            f"| `{name}` | {_format_metric(baseline)} | {_format_metric(corrupted)} | "
            f"{_format_metric(repaired)} | {_format_metric(corrupt_delta)} | {_format_metric(recovery)} |"
        )

    ragas_rows: list[str] = []
    baseline_ragas = baseline_metrics.get("ragas", {})
    corrupted_ragas = corrupted_metrics.get("ragas", {})
    repaired_ragas = repaired_metrics.get("ragas", {})
    for name in _RAGAS_METRIC_NAMES:
        baseline_value = baseline_ragas.get(name)
        corrupted_value = corrupted_ragas.get(name)
        repaired_value = repaired_ragas.get(name)
        ragas_rows.append(
            f"| `{name}` | {_format_metric(baseline_value)} | "
            f"{_format_metric(corrupted_value)} | {_format_metric(repaired_value)} |"
        )

    retrieval_delta = corrupted_metrics.get("retrieval_hit_rate", 0) - baseline_metrics.get("retrieval_hit_rate", 0)
    answer_delta = corrupted_metrics.get("mean_token_f1", 0) - baseline_metrics.get("mean_token_f1", 0)
    repaired_retrieval_delta = repaired_metrics.get("retrieval_hit_rate", 0) - corrupted_metrics.get("retrieval_hit_rate", 0)
    repaired_answer_delta = repaired_metrics.get("mean_token_f1", 0) - corrupted_metrics.get("mean_token_f1", 0)

    impact_statement = (
        "Corruption reduced at least one measured retrieval/answer metric."
        if retrieval_delta < 0 or answer_delta < 0
        else "The measured retrieval and token-F1 metrics did not decrease; no negative agent impact is claimed."
    )
    recovery_statement = (
        "Repair improved at least one degraded retrieval/answer metric."
        if repaired_retrieval_delta > 0 or repaired_answer_delta > 0
        else "Repair did not improve retrieval or token-F1 in this run; investigate the answers artifact before claiming recovery."
    )

    markdown = f"""# Day 10 — Corruption and Repair Comparison

All three states use the same test set, ground truth, evaluator behavior, `top_k`, and embedding model.
Repair is rebuilt from the persisted raw snapshot, not from edited answers or metrics.

## Metric comparison

| Metric | Baseline | Corrupted | Repaired | Corruption Δ | Repair Δ |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Ragas comparison

Ragas uses `{_escape(baseline_ragas.get('model', 'N/A'))}` on the same 16 samples. These LLM-based
scores can vary slightly between runs, so repaired is expected to be equivalent to, not bitwise
identical with, baseline.

| Ragas metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
{chr(10).join(ragas_rows)}

## Quality and freshness signals

| State | Data quality | Freshness |
| --- | --- | --- |
| Baseline | {_escape(_quality_label(baseline_quality))} | {_escape(_freshness_label(baseline_freshness))} |
| Corrupted | {_escape(_quality_label(corrupted_quality))} | {_escape(_freshness_label(corrupted_freshness))} |
| Repaired | {_escape(_quality_label(repaired_quality))} | {_escape(_freshness_label(repaired_freshness))} |

## Evidence-based conclusions

1. **Observed corruption impact:** {impact_statement}
   Retrieval hit-rate Δ = **{retrieval_delta:+.4f}** and mean token-F1 Δ = **{answer_delta:+.4f}**.
2. **Observed repair impact:** {recovery_statement}
   Retrieval hit-rate repair Δ = **{repaired_retrieval_delta:+.4f}** and mean token-F1 repair Δ = **{repaired_answer_delta:+.4f}**.
3. The corrupted quality result is **{_quality_label(corrupted_quality)}** and freshness is
   **{_freshness_label(corrupted_freshness)}**. The repaired state is
   **{_quality_label(repaired_quality)}** with **{_freshness_label(repaired_freshness)}**.

## Audit artifacts

- Corruption events and affected document IDs: `data/results/corruption_log.json`
- Per-question evidence: `data/results/baseline_answers.json`, `corrupted_answers.json`, and `repaired_answers.json`
- Quality/freshness evidence: `data/quality/`
- Separate index manifests: `data/embeddings/`
"""
    write_text(report_path, markdown)
