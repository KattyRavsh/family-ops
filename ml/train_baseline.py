import argparse
import json
from pathlib import Path

import joblib

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

FEATURES = ["days_until_due", "created_weekday", "due_weekday", "has_assignee"]
TARGET = "label_late"
DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "data" / "task_lateness_synthetic.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "synthetic_baseline_metrics.json"
DEFAULT_MODEL = Path(__file__).resolve().parents[1] / "data" / "task_lateness_synthetic.joblib"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()

    if "synthetic" not in args.input.stem.lower():
        parser.error("This demo trainer accepts only a file with 'synthetic' in its filename. Do not use real exports here.")

    df = pd.read_csv(args.input)
    missing = set(FEATURES + [TARGET]) - set(df.columns)
    if missing:
        parser.error(f"Missing required columns: {sorted(missing)}")
    if df.empty or df[TARGET].nunique() != 2:
        parser.error("Dataset must contain examples of both classes (0 and 1). Regenerate with a larger --rows value.")

    X = df[FEATURES]
    y = df[TARGET].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    models = {
        "majority_baseline": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=42),
    }
    metrics = {
        "data_notice": "SYNTHETIC demonstration only; metrics do not estimate performance on real family tasks.",
        "input_file": str(args.input),
        "rows_total": int(len(df)),
        "class_counts": {str(int(k)): int(v) for k, v in y.value_counts().sort_index().items()},
        "test_fraction": 0.25,
        "results": {},
    }

    for name, model in models.items():
        model.fit(X_train, y_train)
        prediction = model.predict(X_test)
        result = {
            "accuracy": float(accuracy_score(y_test, prediction)),
            "f1_macro": float(f1_score(y_test, prediction, average="macro", zero_division=0)),
            "classification_report": classification_report(
                y_test, prediction, output_dict=True, zero_division=0
            ),
        }
        if hasattr(model, "predict_proba"):
            result["roc_auc"] = float(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]))
        metrics["results"][name] = result

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    demo_model = LogisticRegression(max_iter=1000, random_state=42)
    demo_model.fit(X, y)
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": demo_model, "features": FEATURES, "data_kind": "synthetic_demo"},
        args.model_output,
    )
    print("Демонстрационная оценка:")
    for name, result in metrics["results"].items():
        auc = result.get("roc_auc")
        print(f"{name}: accuracy={result['accuracy']:.3f}, macro-F1={result['f1_macro']:.3f}" + (f", ROC-AUC={auc:.3f}" if auc is not None else ""))
    print(f"Подробный отчёт: {args.output}")
    print(f"Демо-модель, обученная на всём синтетическом наборе: {args.model_output}")


if __name__ == "__main__":
    main()
