from datetime import datetime, timedelta

import pandas as pd
import pytest

from ml.evaluate_real import evaluate, FEATURES
from ml.audit_real_data import audit


def make_dataset(n=100):
    rows = []
    start = datetime(2025, 1, 1)
    for i in range(n):
        rows.append({
            "created_at": (start + timedelta(days=i)).isoformat(),
            "days_until_due": 3 + i % 5,
            "created_weekday": i % 7,
            "due_weekday": (i + 3) % 7,
            "has_assignee": i % 2,
            "label_late": (i // 2) % 2,
        })
    return pd.DataFrame(rows)


def test_real_evaluator_uses_chronological_split_and_baseline():
    result = evaluate(make_dataset())
    assert result["data_kind"] == "real_application_history"
    assert result["split"].startswith("chronological")
    assert result["test_rows"] == 20
    assert set(result["results"]) == {"majority_baseline", "logistic_regression"}


def test_real_evaluator_refuses_too_few_rows():
    with pytest.raises(ValueError, match="Need at least"):
        evaluate(make_dataset(30))


def test_real_evaluator_refuses_negative_lead_time():
    df = make_dataset()
    df.loc[0, "days_until_due"] = -2
    with pytest.raises(ValueError, match="already overdue"):
        evaluate(df)


def test_audit_marks_small_dataset_as_not_ready(tmp_path):
    df = make_dataset(9)
    path = tmp_path / "task_lateness.csv"
    df.to_csv(path, index=False)
    result = audit(path)
    assert result["status"] == "collect_more_or_review_data"


def test_audit_rejects_synthetic_filename(tmp_path):
    path = tmp_path / "task_lateness_synthetic.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="not synthetic"):
        audit(path)
