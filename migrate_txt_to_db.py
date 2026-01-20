"""
Migration Script: Text Files to Database

Migrates existing text files with account data into the SQLite database.
Use this for one-time initial import from legacy file format.
"""
import os
import sys
from database import DBManager
from account_manager import AccountManager

# Ensure correct path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)

# Map of file types to (filename, status)
FILES_MAP = {
    "link": ("sheerIDlink.txt", "link_ready"),
    "verified": ("verified_no_card.txt", "verified"),
    "subscribed": ("subscribed.txt", "subscribed"),
    "ineligible": ("ineligible.txt", "ineligible"),
    "error": ("error.txt", "error"),
    "pending": ("eligible_pending.txt", "pending")
}


def migrate():
    """Migrate data from text files to database."""
    print("Starting migration from text files to database...")
    DBManager.init_db()
    
    total_count = 0
    
    for key, (filename, status) in FILES_MAP.items():
        path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(path):
            print(f"File not found, skipping: {filename}")
            continue
            
        print(f"Processing: {filename} (status: {status})...")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            
            count = 0
            for line in lines:
                # Use AccountManager's parsing logic
                email, pwd, rec, sec, link = AccountManager._parse(line)
                if email:
                    # Insert into database
                    DBManager.upsert_account(email, pwd, rec, sec, link, status=status)
                    count += 1
            
            print(f"  -> Successfully imported {count} records")
            total_count += count
            
        except Exception as e:
            print(f"  -> Processing failed: {e}")

    print("-" * 30)
    print(f"Migration complete! Imported {total_count} accounts total.")
    print("Now re-exporting for verification...")
    DBManager.export_to_files()
    print("Verification export complete.")


if __name__ == "__main__":
    migrate()
