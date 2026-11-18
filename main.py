import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()

tasks = []
next_task_id = 1


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks():
    return tasks


@app.post("/tasks")
def create_task(task: TaskCreate):
    global next_task_id

    new_task = {
        "id": next_task_id,
        "title": task.title,
        "completed": False,
    }

    tasks.append(new_task)
    next_task_id += 1

    return new_task


@app.patch("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            task["completed"] = True
            return task

    raise HTTPException(status_code=404, detail="Task not found")


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)