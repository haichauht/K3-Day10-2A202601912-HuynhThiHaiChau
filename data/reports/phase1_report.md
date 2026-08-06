# Day 10 — Baseline Pipeline Report

This report is generated from the same JSON/CSV artifacts produced by the baseline run.

## Source and lineage

| Field | Value |
| --- | --- |
| `source` | Crossref REST API |
| `source_mode` | snapshot |
| `query` | agentic retrieval augmented generation large language model |
| `filter` | from-pub-date:2026-02-07,until-pub-date:2026-08-06,has-abstract:true |
| `requested_records` | 24 |
| `raw_records` | 24 |
| `clean_records` | 24 |
| `cleaning` | {"clean_records": 24, "duplicates_removed": 0, "raw_records": 24, "rejected": {"invalid_published": 0, "missing_paper_id": 0, "missing_summary": 0, "missing_title": 0}} |
| `raw_response_artifact` | C:\VinUni-Lab\K3_Day10_2A202601912_HuynhThiHaiChau\data\raw\crossref_response.json |
| `raw_records_artifact` | C:\VinUni-Lab\K3_Day10_2A202601912_HuynhThiHaiChau\data\raw\crossref_records.json |
| `collection` | papers-baseline |
| `evaluation_samples` | 16 |

## RAG evaluation

| Metric | Value |
| --- | ---: |
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 1.0000 |
| `judge_accuracy` | 1.0000 |
| `mean_judge_score` | 5.0000 |

- Evaluation samples: **16**
- Judge backends: `{"llm": 16}`
- Judge fallback rate: **0.0000**
- Ragas: `{"answer_relevancy": 0.2412391981357942, "context_precision": 0.9774305555236689, "context_recall": 1.0, "faithfulness": 1.0, "model": "gpt-4.1-mini", "samples": 16}`

## Data quality

- Overall status: **PASS**
- Passed checks: **12/12**

| Check | Dimension | Result | Observed | Expectation |
| --- | --- | --- | ---: | --- |
| `minimum_row_count` | volume | PASS | 24 | >= 10 |
| `paper_id_complete` | completeness | PASS | 0 | 0 missing |
| `paper_id_unique` | uniqueness | PASS | 0 | 0 duplicated rows |
| `title_complete` | completeness | PASS | 0 | 0 missing |
| `summary_complete` | completeness | PASS | 0 | 0 missing |
| `summary_minimum_length` | validity | PASS | 0 | 0 summaries shorter than 40 characters |
| `embedding_text_complete` | completeness | PASS | 0 | 0 missing |
| `published_date_valid` | validity | PASS | 0 | 0 invalid |
| `published_not_in_future` | validity | PASS | 0 | 0 dates after the current UTC date |
| `age_days_valid` | validity | PASS | 0 | 0 invalid |
| `no_suspicious_noise_marker` | validity | PASS | 0 | 0 suspicious corruption markers |
| `all_rows_within_freshness_threshold` | freshness | PASS | 0 | 0 rows older than 180 days |

## Freshness

| Signal | Value |
| --- | --- |
| Status | **FRESH (0 stale rows)** |
| Latest publication | 2026-08-06 |
| Oldest publication | 2026-08-06 |
| Threshold | 180 days |
| Total rows | 24 |

## Interpretation

The baseline establishes the reference dataset, fixed evaluation set, collection, metrics, and
observability signals. Corrupted and repaired runs must reuse this evaluation set and retrieval
configuration so any measured change can be attributed to the data state rather than evaluator drift.
