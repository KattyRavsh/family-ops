import argparse
from pathlib import Path

import joblib
import pandas as pd

DEFAULT_MODEL = Path(__file__).resolve().parents[1] / "data" / "task_lateness_synthetic.joblib"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--days-until-due", type=int, required=True,
                        help="Days from creation to due date; must be positive")
    parser.add_argument("--created-weekday", type=int, required=True,
                        help="Weekday of creation: 0=Monday ... 6=Sunday")
    parser.add_argument("--has-assignee", type=int, choices=(0, 1), required=True,
                        help="1 if assigned, otherwise 0")
    args = parser.parse_args()

    if args.days_until_due < 1:
        parser.error("--days-until-due must be at least 1")
    if not 0 <= args.created_weekday <= 6:
        parser.error("--created-weekday must be between 0 and 6")
    if not args.model.exists():
        parser.error(f"Model not found: {args.model}. Run python -m ml.train_baseline first.")

    artifact = joblib.load(args.model)
    if artifact.get("data_kind") != "synthetic_demo":
        parser.error("only synthetic demo model.")
    features = artifact["features"]
    row = {
        "days_until_due": args.days_until_due,
        "created_weekday": args.created_weekday,
        "due_weekday": (args.created_weekday + args.days_until_due) % 7,
        "has_assignee": args.has_assignee,
    }
    X = pd.DataFrame([row], columns=features)
    model = artifact["model"]
    probability = float(model.predict_proba(X)[0, 1])
    predicted_late = int(model.predict(X)[0])

    print(f"Признаки: {row}")
    print(f"Демо-оценка вероятности опоздания: {probability:.1%}")
    print(f"Класс модели: {'опоздание' if predicted_late else 'в срок'}")


if __name__ == "__main__":
    main()
