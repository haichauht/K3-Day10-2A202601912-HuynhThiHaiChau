from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, write_json


CROSSREF_API_URL = "https://api.crossref.org/works"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_markup(value: Any) -> str:
    """Convert Crossref/JATS fragments to plain, normalized text."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", unescape(str(value)))
    return normalize_whitespace(text)


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        return _clean_markup(value[0]) if value else ""
    return _clean_markup(value)


def _date_from_parts(value: Any) -> str:
    """Return an ISO date from a Crossref date-parts object."""
    if not isinstance(value, dict):
        return ""
    parts_list = value.get("date-parts")
    if not isinstance(parts_list, list) or not parts_list or not parts_list[0]:
        return ""
    try:
        parts = [int(part) for part in parts_list[0][:3]]
        year = parts[0]
        month = parts[1] if len(parts) > 1 else 1
        day = parts[2] if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _published_date(item: dict[str, Any]) -> str:
    for field in ("published-print", "published-online", "published", "issued", "created"):
        value = _date_from_parts(item.get(field))
        if value:
            return value
    return ""


def _updated_date(item: dict[str, Any]) -> str:
    indexed = item.get("indexed")
    if isinstance(indexed, dict) and indexed.get("date-time"):
        return str(indexed["date-time"])
    return _date_from_parts(item.get("created"))


def _authors(item: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for author in item.get("author") or []:
        if not isinstance(author, dict):
            continue
        name = normalize_whitespace(
            " ".join(part for part in (str(author.get("given", "")), str(author.get("family", ""))) if part)
        )
        if not name:
            name = _clean_markup(author.get("name"))
        if name and name not in output:
            output.append(name)
    return output


def _pdf_url(item: dict[str, Any]) -> str:
    links = item.get("link") or []
    for link in links:
        if not isinstance(link, dict):
            continue
        content_type = str(link.get("content-type", "")).lower()
        url = str(link.get("URL", ""))
        if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
            return url
    return ""


def _stable_id(item: dict[str, Any], title: str, published: str, authors: list[str]) -> str:
    doi = normalize_whitespace(str(item.get("DOI", ""))).lower()
    if doi:
        return doi
    seed = "|".join((title.lower(), published, authors[0].lower() if authors else ""))
    return f"crossref-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:20]}"


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref response into stable, traceable paper records."""
    message = payload.get("message", {}) if isinstance(payload, dict) else {}
    items = message.get("items", []) if isinstance(message, dict) else []
    if not isinstance(items, list):
        raise ValueError("Invalid Crossref payload: message.items must be a list.")

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _first_text(item.get("title"))
        published = _published_date(item)
        authors = _authors(item)
        paper_id = _stable_id(item, title, published, authors)
        if not title or not paper_id or paper_id in seen_ids:
            continue

        categories = []
        for subject in item.get("subject") or []:
            cleaned = _clean_markup(subject)
            if cleaned and cleaned not in categories:
                categories.append(cleaned)

        abs_url = str(item.get("URL", "") or "")
        resource = item.get("resource")
        if not abs_url and isinstance(resource, dict):
            primary = resource.get("primary")
            if isinstance(primary, dict):
                abs_url = str(primary.get("URL", "") or "")

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=_clean_markup(item.get("abstract")),
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=_updated_date(item),
                abs_url=abs_url,
                pdf_url=_pdf_url(item),
                comment=_first_text(item.get("container-title")) or _clean_markup(item.get("publisher")),
            )
        )
        seen_ids.add(paper_id)
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref with bounded retry and persist both raw artifacts."""
    params = {
        "query.bibliographic": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "VinUni-Day10-Data-Observability-Lab/1.0 (educational use)",
    }

    response: requests.Response | None = None
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = requests.get(CROSSREF_API_URL, params=params, headers=headers, timeout=(10, 45))
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                break
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 8)
            last_error = RuntimeError(f"Crossref returned retryable status {response.status_code}.")
        except requests.RequestException as exc:
            last_error = exc
            delay = min(2**attempt, 8)
        if attempt < 4:
            time.sleep(delay)
    else:
        raise RuntimeError(f"Crossref request failed after 5 attempts: {last_error}") from last_error

    if response is None:
        raise RuntimeError("Crossref request did not produce a response.")
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Crossref returned a non-JSON response.") from exc

    # Persist the exact response before parsing so parser failures remain auditable.
    write_json(settings.paths.raw_api_response, payload)
    records = parse_crossref_payload(payload)
    if not records:
        raise RuntimeError("Crossref returned no usable records for the configured query/filter.")
    write_json(settings.paths.raw_records_json, [record.__dict__ for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load and validate a previously persisted raw-record snapshot."""
    if not path.exists():
        raise FileNotFoundError(f"Raw record snapshot does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Raw record snapshot must contain a JSON list: {path}")

    records: list[PaperRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} is not an object.")
        try:
            records.append(
                PaperRecord(
                    paper_id=str(item["paper_id"]),
                    title=str(item["title"]),
                    summary=str(item.get("summary", "")),
                    authors=[str(value) for value in item.get("authors", [])],
                    categories=[str(value) for value in item.get("categories", [])],
                    primary_category=str(item.get("primary_category", "")),
                    published=str(item.get("published", "")),
                    updated=str(item.get("updated", "")),
                    abs_url=str(item.get("abs_url", "")),
                    pdf_url=str(item.get("pdf_url", "")),
                    comment=str(item.get("comment", "")),
                )
            )
        except KeyError as exc:
            raise ValueError(f"Raw record at index {index} is missing {exc.args[0]!r}.") from exc
    return records
