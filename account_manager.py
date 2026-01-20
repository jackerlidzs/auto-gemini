"""
Account Manager

Handles account state transitions and database operations.
Uses DBManager as the data layer.
"""
from database import DBManager

DBManager.init_db()


class AccountManager:
    """
    Static class for managing account states and file operations.
    All methods update the database and export to text files.
    """
    
    @staticmethod
    def _parse(line):
        """
        Parse an account line into components.
        
        Expected formats:
        - email----password----recovery----secret
        - link----email----password----recovery----secret
        
        Args:
            line: Raw account string with ---- separators
            
        Returns:
            tuple: (email, password, recovery_email, secret_key, link)
        """
        parts = [p.strip() for p in line.split('----') if p.strip()]
        link = None
        email = None
        pwd = None
        rec = None
        sec = None
        
        # Check if first part is a URL
        if parts and "http" in parts[0]:
            link = parts[0]
            parts = parts[1:]
            
        # Find email by looking for @ symbol
        for i, p in enumerate(parts):
            if '@' in p and '.' in p:
                email = p
                if i + 1 < len(parts):
                    pwd = parts[i + 1]
                if i + 2 < len(parts):
                    rec = parts[i + 2]
                if i + 3 < len(parts):
                    sec = parts[i + 3]
                break
        
        return email, pwd, rec, sec, link

    @staticmethod
    def save_link(line):
        """
        Save account with 'link_ready' status (eligible, link extracted).
        
        Args:
            line: Account line containing SheerID link and credentials
        """
        print(f"[AM] save_link called, line: {line[:100] if line else 'None'}...")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='link_ready')
            DBManager.export_to_files()
        else:
            print(f"[AM] save_link: Cannot parse email, skipping")

    @staticmethod
    def move_to_verified(line):
        """
        Move account to 'verified' status (verified but no card bound).
        Saves all fields using upsert.
        
        Args:
            line: Account line with credentials
        """
        print(f"[AM] move_to_verified called")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            # Use upsert instead of update_status to ensure all fields are saved
            DBManager.upsert_account(email, pwd, rec, sec, link, status='verified')
            DBManager.export_to_files()

    @staticmethod
    def move_to_ineligible(line):
        """
        Move account to 'ineligible' status (not eligible for offer).
        
        Args:
            line: Account line with credentials
        """
        print(f"[AM] move_to_ineligible called")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='ineligible')
            DBManager.export_to_files()
        else:
            print(f"[AM] move_to_ineligible: Cannot parse email, skipping")

    @staticmethod
    def move_to_error(line):
        """
        Move account to 'error' status (timeout or other errors).
        
        Args:
            line: Account line with credentials
        """
        print(f"[AM] move_to_error called")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='error')
            DBManager.export_to_files()
        else:
            print(f"[AM] move_to_error: Cannot parse email, skipping")

    @staticmethod
    def move_to_subscribed(line):
        """
        Move account to 'subscribed' status (card bound and subscribed).
        
        Args:
            line: Account line with credentials
        """
        print(f"[AM] move_to_subscribed called")
        email, pwd, rec, sec, link = AccountManager._parse(line)
        if email:
            DBManager.upsert_account(email, pwd, rec, sec, link, status='subscribed')
            DBManager.export_to_files()
            
    @staticmethod
    def remove_from_file_unsafe(file_key, line_or_email):
        """
        Legacy method - no-op with database approach.
        Status updates are handled by database operations.
        """
        pass
