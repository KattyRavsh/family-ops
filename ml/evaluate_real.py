import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, average_precision_score

DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "data" / "task_lateness.csv"
FEATURES = ["days_until_due", "created_weekday", "due_weekday", "has_assignee"]
NUMERIC = ["days_until_due"]
CATEGORICAL = ["created_weekday", "due_weekday", "has_assignee"]
MIN_ROWS = 50
MIN_PER_CLASS = 10


def evaluate(df: pd.DataFrame) -> dict:
    if len(df) < MIN_ROWS:
        raise ValueError(f"Need at least {MIN_ROWS} labeled real rows; got {len(df)}")
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    if df["created_at"].isna().any():
        raise ValueError("created_at contains invalid or missing timestamps")
    df["label_late"] = pd.to_numeric(df["label_late"], errors="coerce")
    if df["label_late"].isna().any() or not set(df["label_late"].unique()).issubset({0, 1}):
        raise ValueError("label_late must contain only 0/1")
    if (pd.to_numeric(df["days_until_due"], errors="coerce") < 0).any():
        raise ValueError("Found task already overdue at creation; re-export and review records")

    df = df.sort_values(["created_at"], kind="stable").reset_index(drop=True)
    split = int(len(df) * 0.8)
    train, test = df.iloc[:split], df.iloc[split:]
    for name, part in (("train", train), ("test", test)):
        counts = part["label_late"].value_counts()
        if len(part) == 0 or any(counts.get(cls, 0) < MIN_PER_CLASS for cls in (0, 1)):
            raise ValueError(f"Chronological {name} split needs at least {MIN_PER_CLASS} examples of each class; got {counts.to_dict()}")

    X_train, y_train = train[FEATURES], train["label_late"].astype(int)
    X_test, y_test = test[FEATURES], test["label_late"].astype(int)
    preprocessor = ColumnTransformer([
        ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC),
        ("categorical", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL),
    ])
    candidates = {
        "majority_baseline": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": Pipeline([
            ("preprocess", preprocessor),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
        ]),
    }
    results = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        row = {
            "accuracy": float(accuracy_score(y_test, pred)),
            "f1_macro": float(f1_score(y_test, pred, average="macro", zero_division=0)),
        }
        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(X_test)[:, 1]
            row["roc_auc"] = float(roc_auc_score(y_test, prob))
            row["average_precision"] = float(average_precision_score(y_test, prob))
        results[name] = row

    return {
        "data_kind": "real_application_history",
        "warning": "Offline historical evaluation only; small single-family data may not generalize.",
        "split": "chronological 80/20 by task created_at; no shuffle",
        "rows_total": len(df),
        "train_rows": len(train),
        "test_rows": len(test),
        "test_start": test["created_at"].min().isoformat(),
        "class_counts_all": {str(int(k)): int(v) for k, v in df["label_late"].value_counts().sort_index().items()},
        "features": FEATURES,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "real_evaluation.json")
    args = parser.parse_args()
    if "synthetic" in args.input.stem.lower():
        parser.error("Real evaluator rejects synthetic input")
    try:
        report = evaluate(pd.read_csv(args.input))
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Отчёт сохранён: {args.output}")


if __name__ == "__main__":
    main()
