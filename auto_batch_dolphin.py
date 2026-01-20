#!/usr/bin/env python3
"""
Auto Batch for Dolphin Anty (Linux)

Headless automation script for running Google One AI Student verification
on Linux VPS using Dolphin Anty browser.

Usage:
    python auto_batch_dolphin.py

Requirements:
    - Dolphin Anty running on the same machine (or accessible via network)
    - accounts.txt with Google accounts
    - proxies.txt (optional) with proxy list
"""
import asyncio
import sys
import os
from typing import Optional, Dict, Tuple

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dolphin_api import DolphinAPI, get_browser_list
from database import DBManager
from account_manager import AccountManager

# Configuration
SEPARATOR = "----"
HEADLESS_MODE = True  # Run without GUI on VPS


def read_accounts(filename: str = "accounts.txt") -> list:
    """Read accounts from file."""
    accounts = []
    separator = SEPARATOR
    
    if not os.path.exists(filename):
        print(f"[ERROR] {filename} not found!")
        return accounts
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Check for separator config
            if line.startswith('separator='):
                separator = line.split('=', 1)[1].strip().strip('"\'')
                continue
            
            # Parse account line
            parts = line.split(separator)
            if len(parts) >= 2:
                account = {
                    'email': parts[0].strip(),
                    'password': parts[1].strip(),
                    'backup': parts[2].strip() if len(parts) > 2 else '',
                    'secret': parts[3].strip() if len(parts) > 3 else ''
                }
                accounts.append(account)
    
    return accounts


def read_proxies(filename: str = "proxies.txt") -> list:
    """Read proxies from file."""
    proxies = []
    
    if not os.path.exists(filename):
        return proxies
    
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse proxy URL: protocol://user:pass@host:port
            proxy = parse_proxy_url(line)
            if proxy:
                proxies.append(proxy)
                print(f"  Loaded proxy: {proxy['host']}:{proxy['port']}")
    
    return proxies


def parse_proxy_url(url: str) -> Optional[Dict]:
    """Parse proxy URL into components."""
    try:
        # Remove protocol
        if '://' in url:
            protocol, rest = url.split('://', 1)
        else:
            protocol = 'http'
            rest = url
        
        # Parse auth and host
        if '@' in rest:
            auth, hostport = rest.rsplit('@', 1)
            if ':' in auth:
                username, password = auth.split(':', 1)
            else:
                username, password = auth, ''
        else:
            hostport = rest
            username, password = '', ''
        
        # Parse host and port
        if ':' in hostport:
            host, port = hostport.rsplit(':', 1)
        else:
            host = hostport
            port = '80'
        
        return {
            'type': protocol,
            'host': host,
            'port': port,
            'username': username,
            'password': password
        }
    except Exception as e:
        print(f"  Failed to parse proxy: {url} - {e}")
        return None


async def process_account(
    api: DolphinAPI,
    account: Dict,
    proxy: Optional[Dict],
    index: int,
    total: int
) -> Tuple[str, str]:
    """
    Process a single account.
    
    Returns:
        Tuple of (result_status, result_message)
    """
    email = account['email']
    print(f"\n{'='*60}")
    print(f"[{index}/{total}] Processing: {email}")
    print(f"{'='*60}")
    
    if proxy:
        print(f"  Using proxy: {proxy['host']}:{proxy['port']}")
    else:
        print(f"  No proxy")
    
    # Build notes/remark string
    parts = [account['email'], account['password']]
    if account.get('backup'):
        parts.append(account['backup'])
    if account.get('secret'):
        parts.append(account['secret'])
    notes = SEPARATOR.join(parts)
    
    # Check for existing profile
    profile_name = f"AutoGemini_{index}"
    existing_profile = api.find_profile_by_notes(email)
    
    if existing_profile:
        profile_id = existing_profile['id']
        print(f"  Found existing profile: {existing_profile.get('name')}")
    else:
        # Create new profile
        print(f"  Creating new profile...")
        profile_id, error = api.create_profile(
            name=profile_name,
            proxy=proxy,
            notes=notes
        )
        if not profile_id:
            return "error", f"Failed to create profile: {error}"
        print(f"  Profile created: {profile_id}")
    
    # Open browser
    print(f"  Opening browser (headless={HEADLESS_MODE})...")
    ws_endpoint, error = api.open_browser(
        profile_id,
        headless=HEADLESS_MODE,
        automation=True
    )
    
    if not ws_endpoint:
        return "error", f"Failed to open browser: {error}"
    
    print(f"  Browser opened. WebSocket: {ws_endpoint[:50]}...")
    
    # Run automation
    try:
        from run_playwright_google import process_browser_with_ws
        
        result = await process_browser_with_ws(
            ws_endpoint=ws_endpoint,
            account_info=account,
            log_callback=lambda msg: print(f"    > {msg}")
        )
        
        status = result.get('status', 'unknown')
        message = result.get('message', '')
        link = result.get('link', '')
        
        # Update database
        db = DBManager()
        if status == 'eligible' and link:
            db.add_or_update_account(
                email=email,
                password=account['password'],
                backup_email=account.get('backup', ''),
                secret_2fa=account.get('secret', ''),
                sheerid_link=link,
                status='eligible_pending'
            )
            return "success", f"Eligible! Link: {link[:50]}..."
        elif status == 'ineligible':
            db.add_or_update_account(
                email=email,
                password=account['password'],
                backup_email=account.get('backup', ''),
                secret_2fa=account.get('secret', ''),
                status='ineligible'
            )
            return "failed", f"Ineligible: {message}"
        else:
            return "error", f"Unknown status: {status} - {message}"
            
    except ImportError:
        # Fallback if run_playwright_google doesn't have ws function
        print("  [WARN] run_playwright_google.process_browser_with_ws not found")
        print("  [WARN] Skipping automation, just testing browser open/close")
        await asyncio.sleep(3)
        return "skipped", "Automation module not ready"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return "error", str(e)
        
    finally:
        # Close browser
        print(f"  Closing browser...")
        api.close_browser(profile_id)


async def main():
    """Main batch processing function."""
    print("=" * 60)
    print("AUTO BATCH - DOLPHIN ANTY (LINUX)")
    print("=" * 60)
    
    # Initialize API
    api = DolphinAPI()
    
    # Check connection
    print("\n[INFO] Checking Dolphin Anty connection...")
    if not api.check_connection():
        print("[ERROR] Cannot connect to Dolphin Anty!")
        print("        Make sure Dolphin Anty is running and Local API is enabled.")
        print("        Default URL: http://localhost:3001")
        return
    print("[OK] Connected to Dolphin Anty")
    
    # Read accounts
    accounts = read_accounts()
    if not accounts:
        print("[ERROR] No accounts found in accounts.txt")
        return
    print(f"[INFO] Found {len(accounts)} accounts")
    
    # Read proxies
    proxies = read_proxies()
    print(f"[INFO] Found {len(proxies)} proxies")
    
    # Process accounts
    results = {
        'success': [],
        'failed': [],
        'error': [],
        'skipped': []
    }
    
    for i, account in enumerate(accounts, 1):
        # Assign proxy (round-robin)
        proxy = proxies[(i-1) % len(proxies)] if proxies else None
        
        # Process account
        status, message = await process_account(api, account, proxy, i, len(accounts))
        
        # Record result
        results[status].append({
            'email': account['email'],
            'message': message
        })
        
        print(f"  [{status.upper()}] {message}")
        
        # Delay between accounts
        if i < len(accounts):
            print("  Waiting 5 seconds before next account...")
            await asyncio.sleep(5)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total: {len(accounts)}")
    print(f"Success: {len(results['success'])}")
    print(f"Failed: {len(results['failed'])}")
    print(f"Errors: {len(results['error'])}")
    print(f"Skipped: {len(results['skipped'])}")
    
    if results['success']:
        print(f"\n[SUCCESS]:")
        for r in results['success']:
            print(f"  - {r['email']}: {r['message']}")
    
    if results['failed']:
        print(f"\n[FAILED]:")
        for r in results['failed']:
            print(f"  - {r['email']}: {r['message']}")
    
    if results['error']:
        print(f"\n[ERROR]:")
        for r in results['error']:
            print(f"  - {r['email']}: {r['message']}")


if __name__ == '__main__':
    asyncio.run(main())
