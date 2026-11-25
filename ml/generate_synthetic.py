import argparse
import csv
import random
from pathlib import Path

FIELDNAMES = [
    "days_until_due",
    "created_weekday",
    "due_weekday",
    "has_assignee",
    "label_late",
]
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "task_lateness_synthetic.csv"


def generate_rows(n: int, seed: int) -> list[dict[str, int]]:
    rng = random.Random(seed)
    rows: list[dict[str, int]] = []
    for _ in range(n):
        created_weekday = rng.randrange(7)
        days_until_due = rng.randint(1, 21)
        due_weekday = (created_weekday + days_until_due) % 7
        has_assignee = int(rng.random() < 0.68)

        probability_late = 0.12
        if days_until_due <= 2:
            probability_late += 0.32
        elif days_until_due <= 5:
            probability_late += 0.14
        if not has_assignee:
            probability_late += 0.16
        if due_weekday in (5, 6):
            probability_late += 0.06
        probability_late = min(probability_late, 0.85)
        label_late = int(rng.random() < probability_late)

        rows.append(
            {
                "days_until_due": days_until_due,
                "created_weekday": created_weekday,
                "due_weekday": due_weekday,
                "has_assignee": has_assignee,
                "label_late": label_late,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.rows < 20:
        parser.error("--rows must be at least 20 for a train/test demonstration")

    rows = generate_rows(args.rows, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    positives = sum(row["label_late"] for row in rows)
    print("Создан синтетический датасет")
    print(f"Строк: {len(rows)}; label 0: {len(rows) - positives}; label 1: {positives}")
    print(f"Файл: {args.output}")


if __name__ == "__main__":
    main()
