# Family Ops

A family task and budget management app built with FastAPI, SQLAlchemy, SQLite, and a lightweight web interface.

The repository also contains an offline ML experimentation pipeline for estimating whether a task will miss its deadline. The ML pipeline is separate from the application: predictions are not currently integrated into the UI or API.

## Features

- Create and manage family tasks, due dates, priorities, and assignees
- Track task completion and completion timestamps
- Manage family members and task comments
- Record income and expenses and view budget summaries
- Generate task drafts from natural-language input using a local Ollama-compatible model
- Run offline ML experiments for task lateness

## Tech stack

- Python 3.14
- FastAPI and Pydantic
- SQLAlchemy and SQLite
- Alembic database migrations
- pandas and scikit-learn
- pytest and GitHub Actions

## Run locally

Create and activate a virtual environment, then install the project dependencies.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Apply database migrations and start the application:

```bash
alembic upgrade head
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` for the web interface. Interactive API documentation is available at `http://127.0.0.1:8000/docs`, and the health endpoint is `http://127.0.0.1:8000/health`.

The application uses a local SQLite database. Database files are local development data and should not be committed.

### Optional: AI task drafts

Task draft generation uses an Ollama-compatible local API at `http://localhost:11434/v1` and the `qwen2.5:3b` model. Start Ollama and make the model available locally to use this feature. The rest of the application and its tests do not require a cloud API key.

## Tests and CI

Run the test suite:

```bash
python -m pytest -q
```

GitHub Actions runs the tests on pushes and pull requests to the `master` branch.

## ML experiments

The ML code is an offline experiment, not a production prediction service.

### Synthetic demonstration

Generate deterministic synthetic data, train and evaluate baseline models, and create a demo model artifact:

```bash
python -m ml.generate_synthetic --rows 2000 --seed 42
python -m ml.train_baseline
python -m ml.predict_task --days-until-due 3 --created-weekday 0 --has-assignee 1
```

The synthetic data is generated from hand-written rules. Metrics from it demonstrate that the pipeline runs; they do **not** estimate performance on real family tasks.

### Reproducible demo results

With `--rows 2000 --seed 42`, the synthetic experiment produced:

| Model | Accuracy | Macro-F1 | ROC-AUC |
|---|---:|---:|---:|
| Majority baseline | 0.756 | 0.431 | 0.500 |
| Logistic regression | 0.752 | 0.445 | 0.632 |

These results verify that the experiment runs end to end; they do not demonstrate
useful predictive performance. In particular, the model has very low recall for
late tasks on this generated dataset. The synthetic generator is a pipeline
demonstration, not a substitute for evaluation on representative real data.


### Evaluation on application history

The real-data workflow exports labeled tasks from the local SQLite database, checks the resulting dataset, and evaluates a baseline and logistic regression using a chronological split:

```bash
python -m ml.export_dataset
python -m ml.audit_real_data
python -m ml.evaluate_real
```

The real-data evaluator uses features derived from the task creation date and deadline. The current assignee is excluded because it may have been assigned after task creation.

The evaluator requires enough labeled examples from both classes. It may stop with an explanatory error while the local history is too small. Do not commit or publish real task exports, database files, or other personal family data.

## ML problem definition

The experiment estimates whether a task with a due date is completed late:

- `0`: completed on or before the due date
- `1`: completed after the due date, or still open after the due date
- Unknown outcome: the task is still open and its due date has not passed; these rows are not used as labeled examples

This is a portfolio-scale engineering experiment. Its purpose is to demonstrate data validation, reproducible training, baseline comparison, temporal evaluation, and automated tests—not to claim a reliable predictor for other families.

## Repository layout

```text
.
├── main.py                 # FastAPI application
├── models.py               # SQLAlchemy database models
├── database.py             # Database engine and sessions
├── migrations/             # Alembic schema migrations
├── ml/                     # Dataset, evaluation, and demo-model scripts
├── static/                 # Web interface
├── tests/                  # Application and ML tests
└── .github/workflows/      # CI workflow
```
