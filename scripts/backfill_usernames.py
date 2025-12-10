import os
from dotenv import load_dotenv
from supabase import create_client, Client
from backend.database import SessionLocal, Task

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
service_key: str = os.environ.get("SERVICE_ROLE_KEY")

if not url or not service_key:
    print("Error: SUPABASE_URL or SERVICE_ROLE_KEY missing in .env")
    exit(1)

# Initialize Supabase with Service Role Key to access Auth Admin
supabase: Client = create_client(url, service_key)

def backfill():
    db = SessionLocal()
    try:
        # Get tasks with missing username
        tasks = db.query(Task).filter(Task.username == None).all()
        print(f"Found {len(tasks)} tasks to update.")
        
        updated_count = 0
        user_cache = {} # Cache user_id -> username to avoid API rate limits

        for task in tasks:
            if not task.user_id:
                continue
                
            username = user_cache.get(task.user_id)
            
            if not username:
                try:
                    # Fetch user from Supabase Auth
                    # Note: supabase-py admin interface might differ slightly by version
                    # We use the admin api to get user by id
                    user_response = supabase.auth.admin.get_user_by_id(task.user_id)
                    
                    if user_response and user_response.user:
                        email = user_response.user.email
                        username = email.split("@")[0]
                        user_cache[task.user_id] = username
                    else:
                        print(f"User not found for ID: {task.user_id}")
                        continue
                except Exception as e:
                    print(f"Error fetching user {task.user_id}: {e}")
                    continue
            
            if username:
                task.username = username
                updated_count += 1
                print(f"Updated Task {task.id} -> {username}")
        
        db.commit()
        print(f"Successfully updated {updated_count} tasks.")
        
    except Exception as e:
        print(f"Error during backfill: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
