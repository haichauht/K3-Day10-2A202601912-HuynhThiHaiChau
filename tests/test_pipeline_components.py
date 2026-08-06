from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from core.config import load_settings
from evaluation.testset import build_test_set
from ingestion.cleaning import CLEAN_COLUMNS, build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records, parse_crossref_payload
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report, generate_phase1_report


def _payload(count: int = 12) -> dict:
    today = datetime.now(UTC).date()
    items = []
    for index in range(count):
        published = today - timedelta(days=index + 1)
        items.append(
            {
                "DOI": f"10.1000/test-{index}",
                "title": [f"Agentic retrieval study number {index}"],
                "abstract": (
                    "<jats:p>This study evaluates retrieval augmented generation with a sufficiently "
                    f"detailed abstract for deterministic testing number {index}.</jats:p>"
                ),
                "author": [{"given": "Ada", "family": f"Researcher{index}"}],
                "subject": ["Artificial Intelligence", "Information Retrieval"],
                "published-online": {"date-parts": [[published.year, published.month, published.day]]},
                "indexed": {"date-time": datetime.now(UTC).isoformat()},
                "URL": f"https://doi.org/10.1000/test-{index}",
                "link": [
                    {
                        "URL": f"https://example.test/paper-{index}.pdf",
                        "content-type": "application/pdf",
                    }
                ],
                "container-title": ["Journal of Testable Pipelines"],
            }
        )
    return {"status": "ok", "message": {"items": items}}


def _records(count: int = 12) -> list[PaperRecord]:
    return parse_crossref_payload(_payload(count))


class _FakeResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_crossref_parse_fetch_and_reload(tmp_path, monkeypatch):
    payload = _payload(3)
    records = parse_crossref_payload(payload)
    assert len(records) == 3
    assert records[0].paper_id == "10.1000/test-0"
    assert "jats" not in records[0].summary.lower()
    assert records[0].authors == ["Ada Researcher0"]
    assert records[0].pdf_url.endswith("paper-0.pdf")

    settings = load_settings(tmp_path)
    monkeypatch.setattr("ingestion.crossref.requests.get", lambda *args, **kwargs: _FakeResponse(payload))
    fetched = fetch_source_records(settings)
    assert fetched == records
    assert settings.paths.raw_api_response.exists()
    assert settings.paths.raw_records_json.exists()
    assert load_raw_records(settings.paths.raw_records_json) == records


def test_clean_testset_corruption_and_observability(tmp_path):
    settings = load_settings(tmp_path)
    assert settings.paths.corrupted_clean_csv.name == "papers_corrupted.csv"
    assert settings.paths.corrupted_clean_json.name == "papers_corrupted.json"
    records = _records()
    clean = build_clean_dataframe(records, datetime.now(UTC))

    assert clean.columns.tolist() == CLEAN_COLUMNS
    assert clean["paper_id"].is_unique
    assert clean["text_for_embedding"].str.contains("Abstract:").all()
    assert clean["age_days"].ge(0).all()
    assert clean.attrs["cleaning_summary"]["raw_records"] == 12

    test_path = tmp_path / "test_set.json"
    test_set = build_test_set(clean, test_path)
    assert len(test_set) == 16
    assert {item["question_type"] for item in test_set} == {"summary", "authors", "date", "categories"}
    assert all(item["ground_truth_doc_ids"][0] in set(clean["paper_id"]) for item in test_set)

    baseline_quality = run_data_quality_checks(clean, settings, "baseline-test")
    baseline_freshness = build_freshness_report(clean, settings, tmp_path / "freshness.json")
    assert baseline_quality["overall_success"] is True
    assert baseline_freshness["status"] == "fresh"

    corruption_log = tmp_path / "corruption.json"
    corrupted = corrupt_clean_dataframe(clean, corruption_log)
    event_types = {event["type"] for event in json.loads(corruption_log.read_text())["events"]}
    assert event_types == {
        "drop_latest_records",
        "blank_summary",
        "inject_summary_noise",
        "truncate_title",
        "make_publication_stale",
        "duplicate_row",
    }
    assert not corrupted["paper_id"].is_unique
    assert corrupted["summary"].eq("").any()
    assert corrupted["published"].eq("2000-01-01").any()
    assert corrupted["age_days"].gt(settings.freshness_threshold_days).any()

    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted-test")
    corrupted_freshness = build_freshness_report(
        corrupted, settings, tmp_path / "corrupted_freshness.json"
    )
    assert corrupted_quality["overall_success"] is False
    assert "paper_id_unique" in corrupted_quality["failed_checks"]
    assert "no_suspicious_noise_marker" in corrupted_quality["failed_checks"]
    assert corrupted_freshness["status"] == "stale"


def test_reports_are_derived_from_payloads(tmp_path):
    metrics = {
        "samples": 4,
        "retrieval_hit_rate": 1.0,
        "mean_token_f1": 1.0,
        "judge_accuracy": 1.0,
        "mean_judge_score": 5.0,
        "judge_backend_counts": {"llm": 4},
        "judge_fallback_rate": 0.0,
        "ragas": {
            "model": "test-ragas-model",
            "samples": 4,
            "answer_relevancy": 0.8,
            "context_precision": 0.9,
            "context_recall": 1.0,
            "faithfulness": 0.95,
        },
    }
    quality = {
        "overall_success": True,
        "passed_checks": 1,
        "failed_checks": [],
        "checks": [
            {
                "name": "paper_id_unique",
                "dimension": "uniqueness",
                "success": True,
                "observed": 0,
                "expectation": "0 duplicated rows",
            }
        ],
    }
    freshness = {
        "status": "fresh",
        "stale_rows": 0,
        "latest_published": "2026-08-01",
        "oldest_published": "2026-07-01",
        "freshness_threshold_days": 180,
        "total_rows": 12,
    }
    baseline_report = tmp_path / "baseline.md"
    generate_phase1_report(baseline_report, {"raw_records": 12}, metrics, quality, freshness)
    assert "retrieval_hit_rate" in baseline_report.read_text(encoding="utf-8")
    assert "PASS" in baseline_report.read_text(encoding="utf-8")

    corrupted_metrics = dict(metrics, retrieval_hit_rate=0.5, mean_token_f1=0.5)
    repaired_metrics = dict(metrics)
    bad_quality = dict(quality, overall_success=False, failed_checks=["paper_id_unique"])
    bad_freshness = dict(freshness, status="stale", stale_rows=1)
    comparison_report = tmp_path / "comparison.md"
    generate_corruption_report(
        comparison_report,
        metrics,
        corrupted_metrics,
        repaired_metrics,
        bad_quality,
        quality,
        bad_freshness,
        freshness,
        baseline_quality=quality,
        baseline_freshness=freshness,
    )
    report_text = comparison_report.read_text(encoding="utf-8")
    assert "-0.5000" in report_text
    assert "Repair improved" in report_text
    assert "Ragas comparison" in report_text
    assert "`context_precision`" in report_text
