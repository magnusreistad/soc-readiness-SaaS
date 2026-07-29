#!/usr/bin/env python3
"""
scripts/get_test_token.py

Gets a Supabase JWT access token for testing FastAPI endpoints.

Usage:
    python scripts/get_test_token.py --email you@example.com --password yourpassword

The token is printed to stdout so you can copy it into:
  - Swagger UI: http://localhost:8000/api/docs → Authorize → paste token
  - curl: -H "Authorization: Bearer <token>"
"""

import argparse
import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx --break-system-packages")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Get a Supabase JWT token for API testing.")
    parser.add_argument("--email",    required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key     = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not anon_key:
        print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")
        sys.exit(1)

    url = f"{supabase_url}/auth/v1/token?grant_type=password"

    resp = httpx.post(
        url,
        headers={
            "apikey":       anon_key,
            "Content-Type": "application/json",
        },
        json={
            "email":    args.email,
            "password": args.password,
        },
        timeout=10,
    )

    if resp.status_code != 200:
        print(f"ERROR: Auth failed ({resp.status_code})")
        print(resp.text)
        sys.exit(1)

    data         = resp.json()
    access_token = data.get("access_token")
    user_email   = data.get("user", {}).get("email")

    print(f"\n  Signed in as: {user_email}")
    print(f"\n  Access token (copy this):\n")
    print(f"  {access_token}")
    print(f"\n  Use in Swagger UI:")
    print(f"  1. Go to http://localhost:8000/api/docs")
    print(f"  2. Click 'Authorize' (top right)")
    print(f"  3. Paste the token above into the 'HTTPBearer' field")
    print(f"  4. Click Authorize → Close")
    print(f"  5. All authenticated endpoints will now work\n")


if __name__ == "__main__":
    main()