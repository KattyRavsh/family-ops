import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from database import SessionLocal
from models import FamilyMemberModel, TaskModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import date


app = FastAPI()


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


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    completed: bool
    due_date: date | None = None
    assigned_member_id: int | None


class FamilyMemberCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


class FamilyMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


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
def get_tasks(db: Session = Depends(get_db)):
    statement = select(TaskModel).order_by(TaskModel.id)
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

    new_task = TaskModel(
        title=task.title,
        due_date=task.due_date,
        assigned_member_id=task.assigned_member_id,
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

    task.completed = True
    db.commit()
    db.refresh(task)

    return task


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)