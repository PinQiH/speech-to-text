import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_KEY missing in .env")
    exit(1)

supabase: Client = create_client(url, key)

email = "admin@test.com"
password = "password123" # We will try to sign up or sign in with this

print(f"Testing Auth for {email}...")

try:
    # Try to sign in first
    print("Attempting Sign In...")
    response = supabase.auth.sign_in_with_password({"email": email, "password": password})
    print("Sign In Successful!")
    print(f"User ID: {response.user.id}")
except Exception as e:
    print(f"Sign In Failed: {e}")
    
    # If sign in failed, maybe try register?
    # But we don't want to spam if it's a 500 error.
    if "500" in str(e):
        print("CRITICAL: Received 500 Internal Server Error from Supabase.")
    else:
        print("Attempting Sign Up (just in case)...")
        try:
            response = supabase.auth.sign_up({"email": email, "password": password})
            print("Sign Up Successful!")
            print(f"User ID: {response.user.id}")
        except Exception as signup_e:
            print(f"Sign Up Failed: {signup_e}")
