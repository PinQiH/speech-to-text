from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Construct Supabase Connection String
# Format: postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
# We assume SUPABASE_URL is like https://[PROJECT-REF].supabase.co
SUPABASE_URL = os.getenv("SUPABASE_URL")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD")

if SUPABASE_URL and DB_PASSWORD:
    project_ref = SUPABASE_URL.split("://")[1].split(".")[0]
    SQLALCHEMY_DATABASE_URL = f"postgresql://postgres:{DB_PASSWORD}@db.{project_ref}.supabase.co:5432/postgres"
else:
    # Fallback to local sqlite if env vars missing (for safety)
    SQLALCHEMY_DATABASE_URL = "sqlite:///./tasks.db"

# Supabase requires SSL mode usually, but psycopg2 might handle it. 
# If issues arise, we might need connect_args={'sslmode':'require'}
connect_args = {}
if "sqlite" in SQLALCHEMY_DATABASE_URL:
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    audio_path = Column(String) # Relative path to media file
    status = Column(String, default="pending") # pending, transcribing, correcting, summarizing, completed, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # User Relationship - Store Supabase Auth UUID
    user_id = Column(String, index=True)
    username = Column(String, nullable=True) # Store username for display 
    
    # Raw Data (Whisper)
    raw_transcription = Column(Text, nullable=True)
    raw_subtitles = Column(Text, nullable=True)
    raw_segments = Column(JSON, nullable=True)
    
    # Corrected Data (Gemini)
    corrected_transcription = Column(Text, nullable=True)
    corrected_subtitles = Column(Text, nullable=True)
    corrected_segments = Column(JSON, nullable=True)
    
    # Summary (Gemini)
    summary = Column(Text, nullable=True)

    # Diarization (Pyannote)
    diarization = Column(JSON, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
