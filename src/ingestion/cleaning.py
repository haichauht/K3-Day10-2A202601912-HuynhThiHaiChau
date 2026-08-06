from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
import re
from typing import Iterable

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "authors_joined",
    "categories",
    "categories_joined",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "abs_url",
    "pdf_url",
    "comment",
    "text_for_embedding",
]


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", unescape(str(value)))
    return normalize_whitespace(text)


def _clean_list(values: Iterable[object] | object, fallback: str) -> list[str]:
    if isinstance(values, str) or not isinstance(values, Iterable):
        values = [values]
    output: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output or [fallback]


def build_embedding_text(
    title: str,
    summary: str,
    authors_joined: str,
    categories_joined: str,
    published: str,
) -> str:
    """Build the single canonical text representation used by all indexes."""
    return "\n".join(
        (
            f"Title: {title}",
            f"Abstract: {summary}",
            f"Authors: {authors_joined}",
            f"Categories: {categories_joined}",
            f"Published: {published}",
        )
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw records into the stable contract consumed by RAG and checks."""
    if not records:
        raise ValueError("Cannot build a cleaned dataset from an empty record list.")

    run_timestamp = pd.Timestamp(run_date)
    if run_timestamp.tzinfo is None:
        run_timestamp = run_timestamp.tz_localize(UTC)
    else:
        run_timestamp = run_timestamp.tz_convert(UTC)

    rows: list[dict[str, object]] = []
    rejected = {"missing_paper_id": 0, "missing_title": 0, "missing_summary": 0, "invalid_published": 0}
    for record in records:
        paper_id = _clean_text(record.paper_id).lower()
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        if not paper_id:
            rejected["missing_paper_id"] += 1
            continue
        if not title:
            rejected["missing_title"] += 1
            continue
        if not summary:
            rejected["missing_summary"] += 1
            continue

        published_timestamp = pd.to_datetime(record.published, errors="coerce", utc=True)
        if pd.isna(published_timestamp):
            rejected["invalid_published"] += 1
            continue
        published = published_timestamp.date().isoformat()
        updated_timestamp = pd.to_datetime(record.updated, errors="coerce", utc=True)
        updated = "" if pd.isna(updated_timestamp) else updated_timestamp.isoformat()
        authors = _clean_list(record.authors, "Unknown author")
        categories = _clean_list(record.categories, "Uncategorized")
        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        age_days = max(0, int((run_timestamp.normalize() - published_timestamp.normalize()).days))

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": _clean_text(record.primary_category) or categories[0],
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "summary_chars": len(summary),
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
                "text_for_embedding": build_embedding_text(
                    title, summary, authors_joined, categories_joined, published
                ),
            }
        )

    if not rows:
        raise ValueError(f"All {len(records)} raw records were rejected during cleaning: {rejected}")

    dataframe = pd.DataFrame(rows, columns=CLEAN_COLUMNS)
    before_deduplication = len(dataframe)
    dataframe = dataframe.drop_duplicates(subset=["paper_id"], keep="first")
    duplicates_removed = before_deduplication - len(dataframe)
    dataframe = dataframe.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    dataframe.attrs["cleaning_summary"] = {
        "raw_records": len(records),
        "clean_records": len(dataframe),
        "duplicates_removed": duplicates_removed,
        "rejected": rejected,
    }
    return dataframe
