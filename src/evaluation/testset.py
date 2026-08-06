from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create a deterministic factual test set grounded only in cleaned rows."""
    missing_columns = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cleaned dataframe is missing test-set columns: {missing_columns}")
    if len(df) < 2:
        raise ValueError("At least two cleaned documents are required to build a test set.")

    candidates = df.head(min(4, len(df))).copy()
    samples: list[dict[str, Any]] = []
    question_number = 1
    for row in candidates.to_dict(orient="records"):
        title = normalize_whitespace(str(row["title"]))
        paper_id = str(row["paper_id"])
        questions = (
            ("summary", f'What is the main finding or topic of "{title}"?', first_sentence(str(row["summary"]))),
            ("authors", f'Who authored "{title}"?', str(row["authors_joined"])),
            ("date", f'When was "{title}" published?', str(row["published"])),
            ("categories", f'What categories are associated with "{title}"?', str(row["categories_joined"])),
        )
        for question_type, question, ground_truth in questions:
            ground_truth = normalize_whitespace(ground_truth)
            if not ground_truth:
                continue
            samples.append(
                {
                    "id": f"q-{question_number:03d}-{question_type}",
                    "question_type": question_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": [paper_id],
                }
            )
            question_number += 1

    if not samples:
        raise ValueError("No valid evaluation samples could be generated.")
    write_json(output_path, samples)
    return samples
