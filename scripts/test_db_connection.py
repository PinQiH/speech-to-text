import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add parent directory to path to allow importing from backend if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_connection():
    print("Loading environment variables...")
    load_dotenv()
    
    # Try to get DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")
    
    # If not found, try to construct it like backend/database.py does
    if not database_url:
        print("DATABASE_URL not found in .env, attempting to construct from SUPABASE_URL and DATABASE_PASSWORD...")
        supabase_url = os.getenv("SUPABASE_URL")
        db_password = os.getenv("DATABASE_PASSWORD")
        
        if supabase_url and db_password:
            try:
                project_ref = supabase_url.split("://")[1].split(".")[0]
                database_url = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"
                print(f"Constructed URL using project ref: {project_ref}")
            except Exception as e:
                print(f"Error constructing URL: {e}")
        else:
            print("Error: Could not find SUPABASE_URL and DATABASE_PASSWORD in .env")
            return

    # Mask password for printing
    if database_url and "@" in database_url:
        masked_url = database_url.split("@")[1]
        print(f"Attempting to connect to: ...@{masked_url}")
    else:
        print(f"Attempting to connect to: {database_url}")

    try:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("\nSUCCESS: Connection established!")
            print(f"Test query result: {result.scalar()}")
    except Exception as e:
        print("\nFAILURE: Could not connect to the database.")
        print(f"Error details: {str(e)}")

if __name__ == "__main__":
    test_connection()
