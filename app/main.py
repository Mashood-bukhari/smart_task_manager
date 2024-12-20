import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, HTTPException
from typing import Optional
from app.schema import Task, TaskResponse
import openai
import os
from datetime import datetime
import asyncio

# FastAPI App initialization
app = FastAPI()

TASKS_COLLECTION = 'tasks'

cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not cred_path:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")

openai.api_key = os.getenv("OPENAI_API_KEY")


def initialize_firebase():
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully!")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")

# Connect to Firestore
def get_firestore_client():
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error connecting to Firestore: {e}")
        return None

async def chat_completion(prompt, token):
    response = await asyncio.to_thread(openai.chat.completions.create,
                                            model="gpt-4o-mini",
                                            messages=prompt,
                                            max_tokens=token)
    return response

# Firebase initialization
initialize_firebase()
db = get_firestore_client()


@app.get("/tasks", response_model=list[TaskResponse])
async def get_tasks():
    try:
        tasks_ref = db.collection(TASKS_COLLECTION)
        tasks = [
            {**doc.to_dict(), "id": doc.id}
            for doc in tasks_ref.stream()
        ]
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks", response_model=TaskResponse)
async def create_task(task: Task):
    try:
        doc_ref = db.collection(TASKS_COLLECTION).document()
        created_at = datetime.utcnow().isoformat()

        # AI Integration: Categorization
        prompt = [
            {
                "role": "user",
                "content": f'Categorize the following task based on its title and description:\n'
                        f'Title: {task.title}\nDescription: {task.description}\n'
                        'Provide a single-word category.'
            }
        ]
        
        response = await chat_completion(prompt=prompt,token= 10)
        category = response.choices[0].message.content

        task_data = {
            "title": task.title,
            "description": task.description,
            "category": category,
            "summary": "",
            "created_at": created_at,
        }

        doc_ref.set(task_data)
        task_data["id"] = doc_ref.id
        return task_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    try:
        doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Task not found")
        return {**doc.to_dict(), "id": doc.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/tasks/{task_id}/summarize", response_model=TaskResponse)
async def summarize_task(task_id: str):
    try:
        doc_ref = db.collection(TASKS_COLLECTION).document(task_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = doc.to_dict()
        # AI Integration: Summarization
        prompt = [
            {
                "role": "user",
                "content": 'Summarize the following task description:\n'
                        f'Description: {task_data["description"]}\nProvide a summary on description.'
            }
        ]
        response = await chat_completion(prompt=prompt, token=25)
        
        summary = response.choices[0].message.content
        
        task_data["summary"] = summary
        doc_ref.update({"summary": summary})

        return {**task_data, "id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
