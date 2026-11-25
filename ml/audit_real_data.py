import argparse
import json
from pathlib import Path

import pandas as pd

DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "data" / "task_lateness.csv"
REQUIRED = ["created_at", "days_until_due", "created_weekday", "due_weekday", "has_assignee", "label_late"]


def audit(path: Path) -> dict:
    if "synthetic" in path.stem.lower():
        raise ValueError("Expected real task_lateness.csv, not synthetic input")
    df = pd.read_csv(path)
    missing_columns = sorted(set(REQUIRED) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    if df.empty:
        return {"rows": 0, "status": "no_labeled_examples", "message": "Экспорт пока пуст."}

    numeric = ["days_until_due", "created_weekday", "due_weekday", "has_assignee", "label_late"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    invalid = int(df[numeric].isna().any(axis=1).sum())
    class_counts = {str(int(k)): int(v) for k, v in df["label_late"].dropna().value_counts().sort_index().items()}
    duplicates = int(df.duplicated(subset=numeric).sum())
    overdue_at_creation = int((df["days_until_due"] < 0).sum())
    enough_for_demo_eval = len(df) >= 50 and min(class_counts.get("0", 0), class_counts.get("1", 0)) >= 10

    return {
        "rows": int(len(df)),
        "class_counts": class_counts,
        "invalid_numeric_rows": invalid,
        "duplicate_feature_rows_review": duplicates,
        "negative_days_until_due": overdue_at_creation,
        "status": "candidate_for_temporal_evaluation" if enough_for_demo_eval and invalid == 0 and overdue_at_creation == 0 else "collect_more_or_review_data",
        "minimum_for_temporal_evaluation": {"rows": 50, "examples_per_class": 10},
        "note": "Threshold is a guardrail for an initial experiment, not a statistical guarantee.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "real_data_audit.json")
    args = parser.parse_args()
    try:
        report = audit(args.input)
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Отчёт сохранён: {args.output}")


if __name__ == "__main__":
    main()
