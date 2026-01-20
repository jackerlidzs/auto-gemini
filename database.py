"""
Database Manager

SQLite database layer for account management.
Handles all database operations including CRUD and file import/export.
"""
import sqlite3
import os
import sys
import threading

# Database path configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
DB_PATH = os.path.join(BASE_DIR, "accounts.db")

# Thread lock for database operations
lock = threading.Lock()


class DBManager:
    """
    Static database manager class.
    Provides methods for account CRUD operations and file synchronization.
    """
    
    @staticmethod
    def get_connection():
        """
        Get a SQLite database connection.
        
        Returns:
            sqlite3.Connection: Database connection with Row factory
        """
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_db():
        """
        Initialize the database.
        Creates accounts table if not exists and imports data from files if empty.
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            # Create accounts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    email TEXT PRIMARY KEY,
                    password TEXT,
                    recovery_email TEXT,
                    secret_key TEXT,
                    verification_link TEXT,
                    status TEXT DEFAULT 'pending',
                    message TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Check for existing data
            cursor.execute("SELECT count(*) FROM accounts")
            count = cursor.fetchone()[0]
            
            conn.commit()
            conn.close()
        
        # Release lock before importing to avoid deadlock if import calls methods that use lock
        if count == 0:
            DBManager.import_from_files()

    @staticmethod
    def _simple_parse(line):
        """
        Parse an account info line using fixed separator.
        Default separator: ----
        
        Args:
            line: Raw account string
            
        Returns:
            tuple: (email, password, recovery_email, secret_key, link)
        """
        import re
        
        # Remove comments
        if '#' in line:
            line = line.split('#')[0].strip()
        
        if not line:
            return None, None, None, None, None
        
        # Identify HTTP links
        link = None
        link_match = re.search(r'https?://[^\s]+', line)
        if link_match:
            link = link_match.group()
            # Remove link and continue parsing
            line = line.replace(link, '').strip()
        
        # Use fixed separator (default ----)
        # Try ---- first, then fall back to other common separators
        separator = '----'
        if separator not in line:
            # Try other separators
            for sep in ['---', '|', ',', ';', '\t']:
                if sep in line:
                    separator = sep
                    break
        
        parts = line.split(separator)
        parts = [p.strip() for p in parts if p.strip()]
        
        email = None
        pwd = None
        rec = None
        sec = None
        
        # Assign in fixed order
        if len(parts) >= 1:
            email = parts[0]
        if len(parts) >= 2:
            pwd = parts[1]
        if len(parts) >= 3:
            rec = parts[2]
        if len(parts) >= 4:
            sec = parts[3]
        
        return email, pwd, rec, sec, link

    @staticmethod
    def import_from_files():
        """
        Import data from existing text files to database (for initialization).
        """
        count_total = 0
        
        # 1. First import from accounts.txt (using new parsing method)
        accounts_path = os.path.join(BASE_DIR, "accounts.txt")
        if os.path.exists(accounts_path):
            try:
                # Use read_accounts function from create_window
                from create_window import read_accounts
                accounts = read_accounts(accounts_path)
                
                print(f"Read {len(accounts)} accounts from accounts.txt")
                
                for account in accounts:
                    email = account.get('email', '')
                    pwd = account.get('password', '')
                    rec = account.get('backup_email', '')
                    sec = account.get('2fa_secret', '')
                    
                    if email:
                        # New accounts default to 'pending' status
                        DBManager.upsert_account(email, pwd, rec, sec, None, status='pending')
                        count_total += 1
                
                print(f"Successfully imported {count_total} accounts (status: pending)")
            except Exception as e:
                print(f"Error importing from accounts.txt: {e}")
        
        # 2. Import from status files (overrides status from accounts.txt)
        files_map = {
            "link_ready": "sheerIDlink.txt",
            "verified": "verified_no_card.txt",
            "subscribed": "subscribed.txt",
            "ineligible": "ineligible.txt",
            "error": "error.txt"
        }
        
        # Legacy Chinese filenames for backward compatibility
        files_map_legacy = {
            "verified": "verified_unbound.txt",
            "subscribed": "subscribed.txt",
            "ineligible": "ineligible.txt",
            "error": "error.txt"
        }
        
        count_status = 0
        for status, filename in files_map.items():
            path = os.path.join(BASE_DIR, filename)
            # Check legacy filename if English not found
            if not os.path.exists(path) and status in files_map_legacy:
                path = os.path.join(BASE_DIR, files_map_legacy[status])
            if not os.path.exists(path): 
                continue
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('#')]
                
                for line in lines:
                    email, pwd, rec, sec, link = DBManager._simple_parse(line)
                    if email:
                        DBManager.upsert_account(email, pwd, rec, sec, link, status=status)
                        count_status += 1
            except Exception as e:
                print(f"Error importing from {filename}: {e}")
        
        if count_status > 0:
            print(f"Imported/updated {count_status} accounts from status files")
        
        total = count_total + count_status
        if total > 0:
            print(f"Database initialization complete, processed {total} records")

    @staticmethod
    def upsert_account(email, password=None, recovery_email=None, secret_key=None, 
                       link=None, status=None, message=None):
        """
        Insert or update an account record.
        
        Args:
            email: Account email (primary key)
            password: Account password
            recovery_email: Recovery/backup email
            secret_key: 2FA secret key
            link: SheerID verification link
            status: Account status
            message: Status message
        """
        if not email: 
            print(f"[DB] upsert_account: email is empty, skipping")
            return
            
        try:
            with lock:
                conn = DBManager.get_connection()
                cursor = conn.cursor()
                
                # Check if record exists
                cursor.execute("SELECT * FROM accounts WHERE email = ?", (email,))
                exists = cursor.fetchone()
                
                if exists:
                    # Build update statement - use 'is not None' instead of truthiness check
                    fields = []
                    values = []
                    if password is not None:
                        fields.append("password = ?")
                        values.append(password)
                    if recovery_email is not None:
                        fields.append("recovery_email = ?")
                        values.append(recovery_email)
                    if secret_key is not None:
                        fields.append("secret_key = ?")
                        values.append(secret_key)
                    if link is not None:
                        fields.append("verification_link = ?")
                        values.append(link)
                    if status is not None:
                        fields.append("status = ?")
                        values.append(status)
                    if message is not None:
                        fields.append("message = ?")
                        values.append(message)
                    
                    if fields:
                        fields.append("updated_at = CURRENT_TIMESTAMP")
                        values.append(email)
                        sql = f"UPDATE accounts SET {', '.join(fields)} WHERE email = ?"
                        cursor.execute(sql, values)
                        print(f"[DB] Updated account: {email}, status: {status}")
                else:
                    # Insert new record
                    cursor.execute('''
                        INSERT INTO accounts (email, password, recovery_email, secret_key, verification_link, status, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (email, password, recovery_email, secret_key, link, status or 'pending', message))
                    print(f"[DB] Inserted new account: {email}, status: {status or 'pending'}")
                
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"[DB ERROR] upsert_account failed, email: {email}, error: {e}")
            import traceback
            traceback.print_exc()

    @staticmethod
    def update_status(email, status, message=None):
        """
        Update account status.
        
        Args:
            email: Account email
            status: New status
            message: Optional status message
        """
        DBManager.upsert_account(email, status=status, message=message)

    @staticmethod
    def get_accounts_by_status(status):
        """
        Get all accounts with a specific status.
        
        Args:
            status: Status to filter by
            
        Returns:
            list: List of account dictionaries
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE status = ?", (status,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
            
    @staticmethod
    def get_all_accounts():
        """
        Get all accounts from database.
        
        Returns:
            list: List of all account dictionaries
        """
        with lock:
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

    @staticmethod
    def export_to_files():
        """
        Export database to traditional text files for easy viewing (overwrites).
        """
        print("[DB] Starting database export to text files...")
        
        files_map = {
            "link_ready": "sheerIDlink.txt",
            "verified": "verified_no_card.txt",
            "subscribed": "subscribed.txt",
            "ineligible": "ineligible.txt",
            "error": "error.txt"
        }
        
        # link_ready accounts also written to eligible_pending.txt as backup
        pending_file = "eligible_pending.txt"
        
        try:
            with lock:
                conn = DBManager.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM accounts")
                rows = cursor.fetchall()
                conn.close()
                
                print(f"[DB] Read {len(rows)} records from database")
                
                # Group by status
                data = {k: [] for k in files_map.keys()}
                pending_data = []  # Handle pending file separately
                
                for row in rows:
                    st = row['status']
                    if st == 'running' or st == 'processing':
                        continue 
                    
                    # Base line construction
                    email = row['email']
                    line_acc = email
                    if row['password']:
                        line_acc += f"----{row['password']}"
                    if row['recovery_email']:
                        line_acc += f"----{row['recovery_email']}"
                    if row['secret_key']:
                        line_acc += f"----{row['secret_key']}"

                    if st == 'link_ready':
                        # Add to link file
                        if row['verification_link']:
                            line_link = f"{row['verification_link']}----{line_acc}"
                            data['link_ready'].append(line_link)
                        
                        # ALSO add to pending file (eligible_pending.txt)
                        pending_data.append(line_acc)
                    
                    elif st in data:
                        data[st].append(line_acc)
                
                # Write main files
                for status, filename in files_map.items():
                    target_path = os.path.join(BASE_DIR, filename)
                    lines = data[status]
                    with open(target_path, 'w', encoding='utf-8') as f:
                        for l in lines:
                            f.write(l + "\n")
                    print(f"[DB] Exported {len(lines)} records to {filename}")
                
                # Write pending file separately
                pending_path = os.path.join(BASE_DIR, pending_file)
                with open(pending_path, 'w', encoding='utf-8') as f:
                    for l in pending_data:
                        f.write(l + "\n")
                print(f"[DB] Exported {len(pending_data)} records to {pending_file}")
                
                print("[DB] Export complete!")
        except Exception as e:
            print(f"[DB ERROR] export_to_files failed: {e}")
            import traceback
            traceback.print_exc()
