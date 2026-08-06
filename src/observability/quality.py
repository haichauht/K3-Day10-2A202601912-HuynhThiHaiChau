from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import safe_slug, write_json


def _check(
    name: str,
    dimension: str,
    success: bool,
    observed: Any,
    expectation: str,
    affected_rows: int = 0,
) -> dict[str, Any]:
    return {
        "name": name,
        "dimension": dimension,
        "success": bool(success),
        "observed": observed,
        "expectation": expectation,
        "affected_rows": int(affected_rows),
    }


def _blank_mask(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df:
        return pd.Series(True, index=df.index, dtype=bool)
    values = df[column]
    return values.isna() | values.astype(str).str.strip().eq("")


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run auditable completeness, uniqueness, validity and freshness gates."""
    row_count = len(df)
    minimum_rows = min(10, max(2, settings.max_results // 2))
    missing_ids = int(_blank_mask(df, "paper_id").sum())
    duplicate_ids = int(df["paper_id"].duplicated(keep=False).sum()) if "paper_id" in df else row_count
    missing_titles = int(_blank_mask(df, "title").sum())
    missing_summaries = int(_blank_mask(df, "summary").sum())
    missing_embedding_text = int(_blank_mask(df, "text_for_embedding").sum())

    if "published" in df:
        parsed_dates = pd.to_datetime(df["published"], errors="coerce", utc=True)
        invalid_dates = int(parsed_dates.isna().sum())
        tomorrow = pd.Timestamp(datetime.now(UTC)).normalize() + pd.Timedelta(days=1)
        future_dates = int(parsed_dates.ge(tomorrow).sum())
    else:
        invalid_dates = row_count
        future_dates = row_count

    if "summary" in df:
        short_summaries = int(df["summary"].fillna("").astype(str).str.len().lt(40).sum())
        noise_rows = int(
            df["summary"]
            .fillna("")
            .astype(str)
            .str.contains(r"(?:CORRUPTED\s+NOISE|zxqv-\d+)", case=False, regex=True)
            .sum()
        )
    else:
        short_summaries = row_count
        noise_rows = row_count

    if "age_days" in df:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
        invalid_ages = int(ages.isna().sum())
        stale_rows = int(ages.gt(settings.freshness_threshold_days).sum()) + invalid_ages
    else:
        invalid_ages = row_count
        stale_rows = row_count

    checks = [
        _check("minimum_row_count", "volume", row_count >= minimum_rows, row_count, f">= {minimum_rows}"),
        _check("paper_id_complete", "completeness", missing_ids == 0, missing_ids, "0 missing", missing_ids),
        _check("paper_id_unique", "uniqueness", duplicate_ids == 0, duplicate_ids, "0 duplicated rows", duplicate_ids),
        _check("title_complete", "completeness", missing_titles == 0, missing_titles, "0 missing", missing_titles),
        _check(
            "summary_complete",
            "completeness",
            missing_summaries == 0,
            missing_summaries,
            "0 missing",
            missing_summaries,
        ),
        _check(
            "summary_minimum_length",
            "validity",
            short_summaries == 0,
            short_summaries,
            "0 summaries shorter than 40 characters",
            short_summaries,
        ),
        _check(
            "embedding_text_complete",
            "completeness",
            missing_embedding_text == 0,
            missing_embedding_text,
            "0 missing",
            missing_embedding_text,
        ),
        _check("published_date_valid", "validity", invalid_dates == 0, invalid_dates, "0 invalid", invalid_dates),
        _check(
            "published_not_in_future",
            "validity",
            future_dates == 0,
            future_dates,
            "0 dates after the current UTC date",
            future_dates,
        ),
        _check("age_days_valid", "validity", invalid_ages == 0, invalid_ages, "0 invalid", invalid_ages),
        _check(
            "no_suspicious_noise_marker",
            "validity",
            noise_rows == 0,
            noise_rows,
            "0 suspicious corruption markers",
            noise_rows,
        ),
        _check(
            "all_rows_within_freshness_threshold",
            "freshness",
            stale_rows == 0,
            stale_rows,
            f"0 rows older than {settings.freshness_threshold_days} days",
            stale_rows,
        ),
    ]
    failed_checks = [item["name"] for item in checks if not item["success"]]
    payload = {
        "report_name": report_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "row_count": row_count,
        "overall_success": not failed_checks,
        "passed_checks": len(checks) - len(failed_checks),
        "failed_checks": failed_checks,
        "checks": checks,
    }
    name = safe_slug(report_name)
    write_json(settings.paths.quality_dir / f"{name}_quality_report.json", payload)
    # Keep a tool-neutral validation artifact under the starter's GX directory.
    write_json(settings.paths.gx_dir / f"{name}_validation.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarize publication freshness using the dataset's actual dates and ages."""
    if "published" not in df or "age_days" not in df:
        raise ValueError("Freshness reporting requires published and age_days columns.")

    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    tomorrow = pd.Timestamp(datetime.now(UTC)).normalize() + pd.Timedelta(days=1)
    invalid_mask = published.isna() | ages.isna() | published.ge(tomorrow)
    invalid_rows = int(invalid_mask.sum())
    stale_mask = ages.gt(settings.freshness_threshold_days) | invalid_mask
    stale_rows = int(stale_mask.sum())
    total_rows = len(df)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "freshness_threshold_days": settings.freshness_threshold_days,
        "latest_published": None if published.dropna().empty else published.max().date().isoformat(),
        "oldest_published": None if published.dropna().empty else published.min().date().isoformat(),
        "stale_rows": stale_rows,
        "invalid_rows": invalid_rows,
        "total_rows": total_rows,
        "stale_ratio": 0.0 if total_rows == 0 else stale_rows / total_rows,
        "is_fresh": total_rows > 0 and stale_rows == 0,
        "status": "fresh" if total_rows > 0 and stale_rows == 0 else "stale" if total_rows > 0 else "unknown",
    }
    write_json(report_path, payload)
    return payload
