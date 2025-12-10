from backend.database import engine, Base, Task
from sqlalchemy import inspect

def check():
    try:
        print("Connecting to DB...")
        connection = engine.connect()
        print("Connected!")
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"Tables: {tables}")
        
        if "tasks" in tables:
            print("Tasks table exists.")
        else:
            print("Tasks table MISSING. Attempting to create...")
            Base.metadata.create_all(bind=engine)
            print("Created tables.")
            
        connection.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
