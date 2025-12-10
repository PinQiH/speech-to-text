from backend.database import engine
from sqlalchemy import text

def add_column():
    try:
        print("Connecting to DB...")
        with engine.connect() as connection:
            print("Adding username column...")
            connection.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS username text;"))
            connection.commit()
            print("Column added successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_column()
