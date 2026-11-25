import uvicorn
import json
import re
import logging

from fastapi import Depends, FastAPI, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError)
from database import SessionLocal
from models import (
    BudgetEntryModel,
    FamilyMemberModel,
    TaskCommentModel,
    TaskModel,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from typing import Literal
from openai import OpenAI, OpenAIError
from pathlib import Path
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles


logging.basicConfig(level=logging.INFO)

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def home_page():
    return FileResponse(STATIC_DIR / "index.html")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    due_date: date | None = None
    assigned_member_id: int | None = None
    created_by_member_id: int | None = None
    category: str | None = Field(default=None, max_length=50)
    priority: Literal["low", "normal", "high"] | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    completed: bool
    due_date: date | None = None
    assigned_member_id: int | None
    created_at: datetime
    completed_at: datetime | None
    created_by_member_id: int | None
    category: str | None
    priority: str | None


class FamilyMemberCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


class FamilyMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TaskDraftRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=2000)


class TaskDraft(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    due_date: date | None = None


class TaskDraftResponse(BaseModel):
    tasks: list[TaskDraft]


class BudgetEntryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    entry_type: Literal["income", "expense"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    transaction_date: date
    member_id: int | None = None


class BudgetEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_type: Literal["income", "expense"]
    amount: Decimal
    category: str
    description: str | None
    transaction_date: date
    member_id: int | None
    created_at: datetime

class BudgetSummary(BaseModel):
    date_from: date | None
    date_to: date | None
    income_total: Decimal
    expense_total: Decimal
    balance: Decimal

class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=100)
    due_date: date | None = None
    assigned_member_id: int | None = None
    category: str | None = Field(default=None, max_length=50)
    priority: Literal["low", "normal", "high"] | None = None


class TaskCommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=2000)
    author_member_id: int | None = None


class TaskCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    author_member_id: int | None
    body: str
    created_at: datetime


client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

WEEKDAY_PATTERNS = {
    "понедельник": 0,
    "вторник": 1,
    "сред": 2,
    "четверг": 3,
    "пятниц": 4,
    "суббот": 5,
    "воскресень": 6,
}


def weekday_due_date(text: str, today: date) -> date | None:
    pattern = (
        r"понедельник\w*|вторник\w*|сред[аыуеой]\w*|"
        r"четверг\w*|пятниц\w*|суббот\w*|воскресень\w*"
    )
    matches = re.findall(pattern, text.lower())

    # Если в запросе несколько дней недели, не делаем неоднозначное предположение.
    if len(matches) != 1:
        return None

    word = matches[0]
    target_weekday = next(
        weekday
        for stem, weekday in WEEKDAY_PATTERNS.items()
        if word.startswith(stem)
    )

    days_until = (target_weekday - today.weekday()) % 7
    return today + timedelta(days=days_until)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/family-members", response_model=FamilyMemberRead)
def create_family_member(
    member: FamilyMemberCreate,
    db: Session = Depends(get_db),
):
    new_member = FamilyMemberModel(name=member.name)

    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return new_member


@app.get("/family-members", response_model=list[FamilyMemberRead])
def get_family_members(db: Session = Depends(get_db)):
    statement = select(FamilyMemberModel).order_by(FamilyMemberModel.id)
    return db.scalars(statement).all()


@app.get("/tasks", response_model=list[TaskRead])
def get_tasks(
    assigned_member_id: int | None = None,
    db: Session = Depends(get_db),
):
    statement = select(TaskModel).order_by(TaskModel.id)

    if assigned_member_id is not None:
        statement = statement.where(
            TaskModel.assigned_member_id == assigned_member_id
        )

    return db.scalars(statement).all()


@app.post("/tasks", response_model=TaskRead)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    if task.assigned_member_id is not None:
        member = db.get(FamilyMemberModel, task.assigned_member_id)
        if member is None:
            raise HTTPException(
                status_code=404,
                detail="Family member not found",
            )

    for member_id in (
            task.assigned_member_id,
            task.created_by_member_id,
    ):
        if member_id is not None and db.get(FamilyMemberModel, member_id) is None:
            raise HTTPException(
                status_code=404,
                detail="Family member not found",
            )

    new_task = TaskModel(
        title=task.title,
        due_date=task.due_date,
        assigned_member_id=task.assigned_member_id,
        created_by_member_id=task.created_by_member_id,
        category=task.category,
        priority=task.priority,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task


@app.patch("/tasks/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.completed:
        task.completed = True
        task.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.commit()
    db.refresh(task)

    return task


@app.post("/tasks/drafts", response_model=TaskDraftResponse)
def create_task_drafts(request: TaskDraftRequest):
    today = date.today().isoformat()

    try:
        response = client.chat.completions.create(
            model="qwen2.5:3b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Извлеки из текста конкретные семейные задачи. "
                        "Сохраняй язык исходного текста. "
                        "Для названия используй исходные слова пользователя: "
                        "не исправляй, не перефразируй и не добавляй новые действия. "
                        "Убирай из названия только слова, обозначающие срок. "
                        "Если срок указан, запиши его отдельным полем due_date в формате YYYY-MM-DD. "
                        "Сегодня: "
                        f"{today}, день недели: {['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'][date.today().weekday()]}. "
                        "Для ближайшего упомянутого дня недели используй ближайшую такую дату."
                        'Верни только JSON такого вида: '
                        '{"tasks":[{"title":"Купить хлеб","due_date":null}]}'
                    ),
                },
                {"role": "user", "content": request.text},
            ],
            response_format={"type": "json_object"},
            max_tokens=1000,
        )

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise HTTPException(
                status_code=502,
                detail="AI returned an empty response",
            )

        data = json.loads(content)
        result = TaskDraftResponse.model_validate(data)

        calculated_due_date = weekday_due_date(request.text, date.today())
        tasks_with_dates = [task for task in result.tasks if task.due_date is not None]

        if calculated_due_date is not None and len(tasks_with_dates) == 1:
            tasks_with_dates[0].due_date = calculated_due_date

        return result

    except (json.JSONDecodeError, ValidationError):
        logging.exception("DeepSeek returned invalid task JSON")
        raise HTTPException(
            status_code=502,
            detail="AI returned an invalid task draft",
        )

    except OpenAIError:
        logging.exception("Ollama Cloud API request failed")
        raise HTTPException(
            status_code=502,
            detail="AI service is temporarily unavailable",
        )


@app.post("/tasks/drafts/accept", response_model=list[TaskRead])
def accept_task_drafts(
    drafts: TaskDraftResponse,
    db: Session = Depends(get_db),
):
    if not drafts.tasks:
        raise HTTPException(
            status_code=422,
            detail="Draft must contain at least one task",
        )

    tasks = [
        TaskModel(
            title=draft.title,
            due_date=draft.due_date,
            assigned_member_id=None,
        )
        for draft in drafts.tasks
    ]

    db.add_all(tasks)
    db.commit()

    for task in tasks:
        db.refresh(task)

    return tasks


@app.post("/budget-entries", response_model=BudgetEntryRead)
def create_budget_entry(
    entry: BudgetEntryCreate,
    db: Session = Depends(get_db),
):
    if entry.member_id is not None:
        member = db.get(FamilyMemberModel, entry.member_id)
        if member is None:
            raise HTTPException(
                status_code=404,
                detail="Family member not found",
            )

    new_entry = BudgetEntryModel(
        entry_type=entry.entry_type,
        amount=entry.amount,
        category=entry.category,
        description=entry.description,
        transaction_date=entry.transaction_date,
        member_id=entry.member_id,
    )

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return new_entry


@app.get("/budget-entries", response_model=list[BudgetEntryRead])
def get_budget_entries(
    entry_type: Literal["income", "expense"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to",
        )

    statement = select(BudgetEntryModel)

    if entry_type is not None:
        statement = statement.where(
            BudgetEntryModel.entry_type == entry_type
        )

    if date_from is not None:
        statement = statement.where(
            BudgetEntryModel.transaction_date >= date_from
        )

    if date_to is not None:
        statement = statement.where(
            BudgetEntryModel.transaction_date <= date_to
        )

    statement = statement.order_by(
        BudgetEntryModel.transaction_date.desc(),
        BudgetEntryModel.id.desc(),
    )

    return db.scalars(statement).all()


@app.get("/budget-summary", response_model=BudgetSummary)
def get_budget_summary(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to",
        )

    statement = select(
        BudgetEntryModel.entry_type,
        BudgetEntryModel.amount,
    )

    if date_from is not None:
        statement = statement.where(
            BudgetEntryModel.transaction_date >= date_from
        )

    if date_to is not None:
        statement = statement.where(
            BudgetEntryModel.transaction_date <= date_to
        )

    entries = db.execute(statement).all()

    income_total = sum(
        (
            amount
            for entry_type, amount in entries
            if entry_type == "income"
        ),
        start=Decimal("0.00"),
    )

    expense_total = sum(
        (
            amount
            for entry_type, amount in entries
            if entry_type == "expense"
        ),
        start=Decimal("0.00"),
    )

    return BudgetSummary(
        date_from=date_from,
        date_to=date_to,
        income_total=income_total,
        expense_total=expense_total,
        balance=income_total - expense_total,
    )


@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int,
    changes: TaskUpdate,
    db: Session = Depends(get_db),
):
    task = db.get(TaskModel, task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if (
        "assigned_member_id" in changes.model_fields_set
        and changes.assigned_member_id is not None
        and db.get(FamilyMemberModel, changes.assigned_member_id) is None
    ):
        raise HTTPException(
            status_code=404,
            detail="Family member not found",
        )

    for field_name, value in changes.model_dump(exclude_unset=True).items():
        setattr(task, field_name, value)

    db.commit()
    db.refresh(task)
    return task


@app.get(
    "/tasks/{task_id}/comments",
    response_model=list[TaskCommentRead],
)
def get_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
):
    if db.get(TaskModel, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    statement = (
        select(TaskCommentModel)
        .where(TaskCommentModel.task_id == task_id)
        .order_by(TaskCommentModel.created_at, TaskCommentModel.id)
    )
    return db.scalars(statement).all()


@app.post(
    "/tasks/{task_id}/comments",
    response_model=TaskCommentRead,
)
def add_task_comment(
    task_id: int,
    comment: TaskCommentCreate,
    db: Session = Depends(get_db),
):
    if db.get(TaskModel, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if (
        comment.author_member_id is not None
        and db.get(FamilyMemberModel, comment.author_member_id) is None
    ):
        raise HTTPException(
            status_code=404,
            detail="Family member not found",
        )

    new_comment = TaskCommentModel(
        task_id=task_id,
        author_member_id=comment.author_member_id,
        body=comment.body,
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(TaskModel, task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    db.query(TaskCommentModel).filter(
        TaskCommentModel.task_id == task_id
    ).delete(synchronize_session=False)

    db.delete(task)
    db.commit()
    return Response(status_code=204)


@app.delete("/budget-entries/{entry_id}", status_code=204)
def delete_budget_entry(
    entry_id: int,
    db: Session = Depends(get_db),
):
    entry = db.get(BudgetEntryModel, entry_id)

    if entry is None:
        raise HTTPException(status_code=404, detail="Budget entry not found")

    db.delete(entry)
    db.commit()
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)