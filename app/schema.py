from pydantic import BaseModel


class Task(BaseModel):
    title: str
    description: str

class TaskResponse(Task):
    id: str
    category: str
    summary: str
    created_at: str