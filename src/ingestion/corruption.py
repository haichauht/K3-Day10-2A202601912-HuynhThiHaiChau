from __future__ import annotations

from datetime import UTC, datetime
import math

import pandas as pd

from core.utils import write_json
from ingestion.cleaning import build_embedding_text


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
    "age_days",
    "summary_chars",
    "text_for_embedding",
}


def _refresh_derived_fields(df: pd.DataFrame) -> None:
    today = pd.Timestamp(datetime.now(UTC)).normalize()
    for index, row in df.iterrows():
        summary = str(row["summary"] or "")
        published_timestamp = pd.to_datetime(row["published"], errors="coerce", utc=True)
        age_days = -1 if pd.isna(published_timestamp) else max(0, int((today - published_timestamp.normalize()).days))
        df.at[index, "summary_chars"] = len(summary)
        df.at[index, "age_days"] = age_days
        df.at[index, "text_for_embedding"] = build_embedding_text(
            str(row["title"]),
            summary,
            str(row["authors_joined"]),
            str(row["categories_joined"]),
            str(row["published"]),
        )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Create deterministic, logged failures across multiple quality dimensions."""
    missing_columns = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot corrupt dataframe; required columns are missing: {missing_columns}")
    if len(df) < 2:
        raise ValueError("At least two rows are required for the corruption scenario.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    baseline_rows = len(corrupted)
    events: list[dict[str, object]] = []

    drop_count = min(max(1, math.ceil(baseline_rows * 0.2)), max(0, baseline_rows - 2))
    dropped_ids = corrupted.head(drop_count)["paper_id"].astype(str).tolist()
    if drop_count:
        corrupted = corrupted.iloc[drop_count:].reset_index(drop=True)
        events.append(
            {
                "type": "drop_latest_records",
                "affected_paper_ids": dropped_ids,
                "count": drop_count,
                "parameter": {"fraction": 0.2},
            }
        )

    def target(position: int) -> int:
        return position % len(corrupted)

    blank_index = target(0)
    blank_id = str(corrupted.at[blank_index, "paper_id"])
    corrupted.at[blank_index, "summary"] = ""
    events.append(
        {
            "type": "blank_summary",
            "affected_paper_ids": [blank_id],
            "count": 1,
            "parameter": {"replacement": "empty string"},
        }
    )

    noise_index = target(1)
    noise_id = str(corrupted.at[noise_index, "paper_id"])
    noise_prefix = "CORRUPTED NOISE zxqv-991 irrelevant tokens. "
    corrupted.at[noise_index, "summary"] = noise_prefix + str(corrupted.at[noise_index, "summary"])
    events.append(
        {
            "type": "inject_summary_noise",
            "affected_paper_ids": [noise_id],
            "count": 1,
            "parameter": {"prefix": noise_prefix.strip()},
        }
    )

    title_index = target(2)
    title_id = str(corrupted.at[title_index, "paper_id"])
    original_title = str(corrupted.at[title_index, "title"])
    truncated_title = original_title[: max(8, min(18, len(original_title) // 3))].rstrip() + "…"
    corrupted.at[title_index, "title"] = truncated_title
    events.append(
        {
            "type": "truncate_title",
            "affected_paper_ids": [title_id],
            "count": 1,
            "parameter": {"original_chars": len(original_title), "new_chars": len(truncated_title)},
        }
    )

    stale_index = target(3)
    stale_id = str(corrupted.at[stale_index, "paper_id"])
    original_published = str(corrupted.at[stale_index, "published"])
    # C4 uses a fixed year-2000 value so the scenario is deterministic and
    # unambiguously violates the freshness threshold on every rerun.
    stale_date = "2000-01-01"
    corrupted.at[stale_index, "published"] = stale_date
    events.append(
        {
            "type": "make_publication_stale",
            "affected_paper_ids": [stale_id],
            "count": 1,
            "parameter": {"before": original_published, "after": stale_date},
        }
    )

    duplicate_index = target(4)
    duplicate_id = str(corrupted.at[duplicate_index, "paper_id"])
    duplicate = corrupted.iloc[[duplicate_index]].copy(deep=True)
    corrupted = pd.concat([corrupted, duplicate], ignore_index=True)
    events.append(
        {
            "type": "duplicate_row",
            "affected_paper_ids": [duplicate_id],
            "count": 1,
            "parameter": {"duplicate_keeps_same_paper_id": True},
        }
    )

    _refresh_derived_fields(corrupted)
    corrupted.attrs["corruption_summary"] = {
        "baseline_rows": baseline_rows,
        "corrupted_rows": len(corrupted),
        "events": events,
    }
    write_json(
        output_log_path,
        {
            "created_at": datetime.now(UTC).isoformat(),
            "deterministic": True,
            "baseline_rows": baseline_rows,
            "corrupted_rows": len(corrupted),
            "unique_rows_after_corruption": int(corrupted["paper_id"].nunique()),
            "events": events,
        },
    )
    return corrupted
