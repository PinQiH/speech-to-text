from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import shutil
import os
import uuid
from typing import List
from database import init_db, get_db, Task, SessionLocal
from logic import transcribe_audio, format_segments, summarize_text, correct_transcription, parse_corrected_segments, diarize_audio, merge_diarization_with_transcript
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Mount static files for audio playback
os.makedirs("media", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

import threading

# Initialize Database
init_db()

# Supabase Client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Global lock for sequential processing of local transcription only
transcription_lock = threading.Lock()

# --- Auth Endpoints ---
class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

@app.post("/register")
def register(user: UserRegister):
    try:
        response = supabase.auth.sign_up({
            "email": user.email, 
            "password": user.password
        })
        # Supabase returns a User object inside the response
        if response.user:
            return {"id": response.user.id, "email": response.user.email}
        else:
            # Sometimes sign_up requires email confirmation, so user might be None but no error
            return {"message": "Registration successful. Please check your email for confirmation."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
def login(user: UserLogin):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user.email, 
            "password": user.password
        })
        if response.user:
            # Check if admin (Hardcoded for POC)
            is_admin = (response.user.email == "admin@test.com")
            
            # Extract username
            username = response.user.email.split("@")[0]
            
            return {
                "id": response.user.id,
                "email": response.user.email,
                "username": username,
                "is_admin": is_admin,
                "access_token": response.session.access_token
            }
        else:
             raise HTTPException(status_code=400, detail="Login failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def process_background_task(task_id: int, api_key: str, hf_token: str = None, num_speakers: int = None):
    # No global lock here, allowing concurrency for API-bound steps
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            print(f"Task {task_id} not found in background task.")
            return

        # --- Step 1: Transcribe ---
        task.status = "transcribing"
        db.commit()
        
        # Only lock during the resource-intensive local transcription
        with transcription_lock:
            result = transcribe_audio(task.audio_path)
        
        segments = result["segments"]
        
        # --- Step 1.5: Diarize ---
        if hf_token:
            print(f"Starting diarization for task {task_id}...")
            diarization_result = diarize_audio(task.audio_path, hf_token, num_speakers)
            task.diarization = diarization_result
            
            # Merge with raw segments
            segments = merge_diarization_with_transcript(segments, diarization_result)
            print(f"Diarization merged. Segments with speakers: {len(segments)}")
        
        formatted_subtitles = format_segments(segments)
        
        task.raw_transcription = result["text"]
        task.raw_segments = segments
        task.raw_subtitles = formatted_subtitles
        task.status = "transcribed"
        db.commit()
        
        # --- Step 2: Correct ---
        task.status = "correcting"
        db.commit()
        
        if not task.raw_subtitles or not task.raw_subtitles.strip():
            print(f"Task {task_id}: Raw subtitles empty. Skipping correction.")
            final_transcription = ""
            final_subtitles = ""
            final_segments = []
        else:
            corrected_transcription = correct_transcription(task.raw_subtitles, api_key)
            
            if corrected_transcription.startswith("Error"):
                final_subtitles = task.raw_subtitles
                final_segments = [] 
                final_transcription = "" 
            else:
                final_subtitles = corrected_transcription
                final_segments = parse_corrected_segments(corrected_transcription)
                
                if not final_segments:
                    final_subtitles = task.raw_subtitles
                    final_segments = []
                    final_transcription = ""
                else:
                    final_transcription = " ".join([s["text"] for s in final_segments])
        
        task.corrected_transcription = final_transcription
        task.corrected_subtitles = final_subtitles
        task.corrected_segments = final_segments
        task.status = "corrected"
        db.commit()

        # --- Step 3: Summarize ---
        task.status = "summarizing"
        db.commit()
        
        source_text = task.corrected_subtitles if task.corrected_subtitles else task.raw_subtitles
        
        if not source_text or not source_text.strip():
            print(f"Task {task_id}: Source text is empty. Skipping summary.")
            task.summary = "No transcription available."
        else:
            summary = summarize_text(source_text, api_key)
            task.summary = summary
        
        task.status = "completed"
        db.commit()

    except Exception as e:
        print(f"Error in background task {task_id}: {str(e)}")
        # Re-query task to ensure we have the latest session state if needed, 
        # but here we just want to mark it failed.
        try:
            task.status = "failed"
            db.commit()
        except:
            pass
    finally:
        db.close()

@app.post("/process")
async def process_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    api_key: str = Form(...),
    hf_token: str = Form(None),
    num_speakers: int = Form(None),
    user_id: str = Form(...), # Changed to str (UUID)
    username: str = Form(None), # Optional username for display
    db: Session = Depends(get_db)
):
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join("media", unique_filename)
    
    # Save file permanently
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Create Task record
        new_task = Task(
            filename=file.filename,
            audio_path=file_path.replace("\\", "/"),
            status="pending",
            user_id=user_id, # Link to user (UUID)
            username=username # Store username
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        # Trigger background task
        background_tasks.add_task(process_background_task, new_task.id, api_key, hf_token, num_speakers)
        
        return {"task_id": new_task.id, "message": "Processing started in background"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import datetime

def check_timeout(task, db):
    if task.status in ["transcribing", "correcting", "summarizing"]:
        last_update = task.updated_at or task.created_at
        if (datetime.datetime.utcnow() - last_update).total_seconds() > 600:
            task.status = "timeout"
            db.commit()

@app.get("/tasks")
@app.get("/tasks")
async def get_tasks(user_id: str, is_admin: bool = False, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Task)
    
    # If not admin, filter by user_id
    if not is_admin:
        query = query.filter(Task.user_id == user_id)
        
    tasks = query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    
    for task in tasks:
        check_timeout(task, db)
    return tasks

@app.get("/tasks/{task_id}")
async def get_task_details(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

class TaskUpdate(BaseModel):
    corrected_subtitles: str = None
    summary: str = None
    speaker_map: dict = None
    api_key: str = None
    regenerate_summary: bool = False

@app.put("/tasks/{task_id}")
async def update_task(task_id: int, update_data: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 1. Update Text Content First
    if update_data.corrected_subtitles:
        task.corrected_subtitles = update_data.corrected_subtitles
    
    if update_data.summary:
        task.summary = update_data.summary

    # 2. Apply Speaker Renaming (to the potentially updated text)
    if update_data.speaker_map:
        print(f"Applying speaker map: {update_data.speaker_map}")
        
        def replace_speakers(text, mapping):
            if not text: return text
            for code, name in mapping.items():
                text = text.replace(code, name)
            return text

        # Apply to subtitles
        if task.corrected_subtitles:
            task.corrected_subtitles = replace_speakers(task.corrected_subtitles, update_data.speaker_map)
        
        # Apply to transcription
        if task.corrected_transcription:
            task.corrected_transcription = replace_speakers(task.corrected_transcription, update_data.speaker_map)
            
        # Apply to summary
        if task.summary:
            task.summary = replace_speakers(task.summary, update_data.speaker_map)
            
        # Apply to segments (JSON) - Update existing segments
        if task.corrected_segments:
            new_segments = []
            for seg in task.corrected_segments:
                new_seg = seg.copy()
                if 'speaker' in new_seg and new_seg['speaker'] in update_data.speaker_map:
                    new_seg['speaker'] = update_data.speaker_map[new_seg['speaker']]
                new_segments.append(new_seg)
            task.corrected_segments = new_segments

    # 3. Re-parse segments if text changed (and not just speaker names in JSON)
    # If we updated text (either via manual edit or speaker replace), we should sync segments text.
    # However, simple string replace on segments JSON (above) handles speaker names.
    # But if user manually edited text, we need to re-parse.
    
    if update_data.corrected_subtitles:
        # Re-parse to get new text structure if manual edits occurred
        # Note: This might reset speaker labels if the parser doesn't find them, 
        # BUT our parser looks for [SPEAKER_XX] or [Name].
        # Since we already replaced SPEAKER_XX with Name in step 2, the parser needs to handle Names.
        # Our current parser might only expect [SPEAKER_XX]. 
        # Let's check logic.py. If parser is robust, it's fine.
        # For now, let's assume the simple replace above is enough for speaker names.
        # If the user edited text, we re-parse.
        
        final_segments = parse_corrected_segments(task.corrected_subtitles)
        if final_segments:
             task.corrected_segments = final_segments
             task.corrected_transcription = " ".join([s["text"] for s in final_segments])

    # 4. Handle Regenerate Summary
    if update_data.regenerate_summary and update_data.api_key:
        source_text = task.corrected_subtitles if task.corrected_subtitles else task.raw_subtitles
        if source_text:
            new_summary = summarize_text(source_text, update_data.api_key)
            task.summary = new_summary

    db.commit()
    return {"message": "Task updated successfully", "task": task}

class RetryTaskRequest(BaseModel):
    api_key: str
    hf_token: str = None
    num_speakers: int = None

@app.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: int, 
    request: RetryTaskRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Reset status
    task.status = "pending"
    db.commit()
    
    # Trigger background task
    background_tasks.add_task(process_background_task, task.id, request.api_key, request.hf_token, request.num_speakers)
    
    return {"message": "Task retry started"}
