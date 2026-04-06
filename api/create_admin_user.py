#!/usr/bin/env python3
"""
Generate a MongoDB document for an admin user and print it as JSON.
Optionally insert it directly into MongoDB with --insert.
"""
import argparse
import base64
import getpass
import json
import uuid
from datetime import UTC, datetime

import bcrypt


def main():
    parser = argparse.ArgumentParser(description="Generate an admin user document for axes")
    parser.add_argument("--username", default="admin", help="Username (default: admin)")
    parser.add_argument("--email", default="admin@local.dev", help="Email (default: admin@local.dev)")
    parser.add_argument("--insert", action="store_true", help="Insert directly into MongoDB")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017", help="MongoDB URI (used with --insert)")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        raise SystemExit(1)

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()

    doc = {
        "user_id": user_id,
        "user_name": args.username,
        "email": args.email,
        "password_hash": password_hash,
        "created_at": created_at,
        "is_admin": True,
    }

    print("\n--- MongoDB document ---")
    print(json.dumps(doc, indent=2))

    credentials_b64 = base64.b64encode(f"{args.username}:{password}".encode()).decode()
    print(f"\n--- Login credentials (base64 for API/admin) ---")
    print(f"credentials: {credentials_b64}")

    if args.insert:
        try:
            from pymongo import MongoClient
        except ImportError:
            print("\nERROR: pymongo is not installed. Run: pip install pymongo")
            raise SystemExit(1)

        client = MongoClient(args.mongo_uri)
        result = client["axes"]["users"].insert_one(doc)
        print(f"\nInserted with _id: {result.inserted_id}")
        client.close()


if __name__ == "__main__":
    main()
