# Day 10 — Corruption and Repair Comparison

All three states use the same test set, ground truth, evaluator behavior, `top_k`, and embedding model.
Repair is rebuilt from the persisted raw snapshot, not from edited answers or metrics.

## Metric comparison

| Metric | Baseline | Corrupted | Repaired | Corruption Δ | Repair Δ |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.0000 | 1.0000 | -1.0000 | 1.0000 |
| `mean_token_f1` | 1.0000 | 0.7921 | 1.0000 | -0.2079 | 0.2079 |
| `judge_accuracy` | 1.0000 | 0.7500 | 1.0000 | -0.2500 | 0.2500 |
| `mean_judge_score` | 5.0000 | 4.0625 | 5.0000 | -0.9375 | 0.9375 |

## Ragas comparison

Ragas uses `gpt-4.1-mini` on the same 16 samples. These LLM-based
scores can vary slightly between runs, so repaired is expected to be equivalent to, not bitwise
identical with, baseline.

| Ragas metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| `answer_relevancy` | 0.2412 | 0.1242 | 0.2469 |
| `context_precision` | 0.9774 | 0.8906 | 0.9774 |
| `context_recall` | 1.0000 | 0.8750 | 1.0000 |
| `faithfulness` | 1.0000 | 0.3438 | 0.9688 |

## Quality and freshness signals

| State | Data quality | Freshness |
| --- | --- | --- |
| Baseline | PASS | FRESH (0 stale rows) |
| Corrupted | FAIL (paper_id_unique, summary_complete, summary_minimum_length, no_suspicious_noise_marker, all_rows_within_freshness_threshold) | STALE (1 stale rows) |
| Repaired | PASS | FRESH (0 stale rows) |

## Evidence-based conclusions

1. **Observed corruption impact:** Corruption reduced at least one measured retrieval/answer metric.
   Retrieval hit-rate Δ = **-1.0000** and mean token-F1 Δ = **-0.2079**.
2. **Observed repair impact:** Repair improved at least one degraded retrieval/answer metric.
   Retrieval hit-rate repair Δ = **+1.0000** and mean token-F1 repair Δ = **+0.2079**.
3. The corrupted quality result is **FAIL (paper_id_unique, summary_complete, summary_minimum_length, no_suspicious_noise_marker, all_rows_within_freshness_threshold)** and freshness is
   **STALE (1 stale rows)**. The repaired state is
   **PASS** with **FRESH (0 stale rows)**.

## Audit artifacts

- Corruption events and affected document IDs: `data/results/corruption_log.json`
- Per-question evidence: `data/results/baseline_answers.json`, `corrupted_answers.json`, and `repaired_answers.json`
- Quality/freshness evidence: `data/quality/`
- Separate index manifests: `data/embeddings/`
