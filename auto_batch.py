"""
Auto Batch Script - Chạy trực tiếp không cần GUI 

Đọc accounts.txt + proxies.txt → Tạo browser windows → Login → Check eligibility
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from create_window import read_accounts, read_proxies, create_browser_window, get_browser_list
from run_playwright_google import process_browser
from bit_api import closeBrowser, deleteBrowser
import time

def main():
    print('='*60)
    print('AUTO BATCH - DIRECT MODE (NO GUI)')
    print('='*60)
    
    # Read accounts
    accounts = read_accounts('accounts.txt')
    print(f'\n[INFO] Found {len(accounts)} accounts to process')
    
    if not accounts:
        print('[ERROR] No accounts found!')
        return
    
    # Read proxies
    proxies = read_proxies('proxies.txt')
    print(f'[INFO] Loaded {len(proxies)} proxies')
    
    results = {
        'success': [],
        'failed': [],
        'errors': []
    }
    
    for i, account in enumerate(accounts, 1):
        email = account['email']
        print(f'\n{"="*60}')
        print(f'[{i}/{len(accounts)}] Processing: {email}')
        print('='*60)
        
        # Get proxy for this account (if available)
        proxy = proxies[i - 1] if i - 1 < len(proxies) else None
        if proxy:
            print(f'  Using proxy: {proxy["type"]}://{proxy["host"]}:{proxy["port"]}')
        else:
            print('  No proxy (direct connection)')
        
        try:
            # Check if browser exists
            browsers = get_browser_list(page=0, pageSize=100)
            browser_id = None
            
            for b in browsers:
                if email in b.get('remark', ''):
                    browser_id = b.get('id')
                    print(f'  Found existing browser: {b.get("name")}')
                    break
            
            # Create new browser if needed
            if not browser_id:
                print('  Creating new browser window...')
                browser_id, error = create_browser_window(
                    account,
                    reference_browser_id=None,
                    proxy=proxy,  # Use proxy here
                    template_config={
                        'name': 'AutoBatch',
                        'proxyType': proxy['type'] if proxy else 'noproxy',
                        'browserFingerPrint': {'coreVersion': '140'}
                    },
                    name_prefix='AutoBatch'
                )
                
                if error:
                    print(f'  [ERROR] Failed to create browser: {error}')
                    results['errors'].append((email, error))
                    continue
                    
                print(f'  Browser created: {browser_id}')
            
            # Run automation
            print('  Starting automation...')
            success, result = process_browser(browser_id, log_callback=lambda m: print(f'    > {m}'))
            
            if success:
                print(f'  [SUCCESS] {result}')
                results['success'].append((email, result))
            else:
                print(f'  [FAILED] {result}')
                results['failed'].append((email, result))
            
            # Close browser after processing
            print('  Closing browser...')
            closeBrowser(browser_id)
            
            # Wait between accounts
            if i < len(accounts):
                print('  Waiting 3 seconds before next account...')
                time.sleep(3)
                
        except Exception as e:
            print(f'  [ERROR] Exception: {e}')
            results['errors'].append((email, str(e)))
    
    # Print summary
    print('\n' + '='*60)
    print('SUMMARY')
    print('='*60)
    print(f'Total: {len(accounts)}')
    print(f'Success: {len(results["success"])}')
    print(f'Failed: {len(results["failed"])}')
    print(f'Errors: {len(results["errors"])}')
    
    if results['success']:
        print('\n[SUCCESS]:')
        for email, msg in results['success']:
            print(f'  - {email}: {msg}')
    
    if results['failed']:
        print('\n[FAILED]:')
        for email, msg in results['failed']:
            print(f'  - {email}: {msg}')
    
    if results['errors']:
        print('\n[ERRORS]:')
        for email, msg in results['errors']:
            print(f'  - {email}: {msg}')

if __name__ == '__main__':
    main()
