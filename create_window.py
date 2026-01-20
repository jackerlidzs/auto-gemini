"""
BitBrowser Window Creation Module

Creates new browser windows/profiles based on reference template.
Reads account information from accounts.txt file.
"""
import requests
import json
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# BitBrowser API endpoint
url = "http://127.0.0.1:54345"
headers = {
    'Content-Type': 'application/json',
    'x-api-key': '91d1df9772a24f7ba67646c327727086'  # BitBrowser API Token
}


def read_proxies(file_path: str) -> list:
    """
    Read proxy configuration file.
    
    Args:
        file_path: Path to proxy file
        
    Returns:
        List of proxy dicts: {'type': 'http/socks5', 'host': '', 'port': '', 'username': '', 'password': ''}
        Returns empty list if no proxies found
        
    Supported formats:
        socks5://user:pass@host:port
        http://user:pass@host:port
        https://user:pass@host:port
    """
    proxies = []
    
    if not os.path.exists(file_path):
        return proxies
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Match socks5, http, or https protocols
                match = re.match(r'^(socks5|http|https)://([^:]+):([^@]+)@([^:]+):(\d+)$', line)
                if match:
                    proxy_type = match.group(1)
                    # BitBrowser uses 'http' for both http and https proxies
                    if proxy_type == 'https':
                        proxy_type = 'http'
                    proxies.append({
                        'type': proxy_type,
                        'host': match.group(4),
                        'port': match.group(5),
                        'username': match.group(2),
                        'password': match.group(3)
                    })
                    print(f"  Loaded proxy: {proxy_type}://{match.group(4)}:{match.group(5)}")
    except Exception as e:
        print(f"Error reading proxies: {e}")
    
    return proxies


def read_separator_config(file_path: str) -> str:
    """
    Read separator configuration from file header.
    
    Format: separator="----"
    
    Returns:
        Separator string, defaults to "----"
    """
    default_sep = "----"
    
    if not os.path.exists(file_path):
        return default_sep
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Look for separator config line
                if line.startswith('separator='):
                    # Extract content within quotes
                    match = re.search(r'["\'](.+?)["\']', line)
                    if match:
                        return match.group(1)
                # Stop searching if we hit non-comment, non-config line
                if not line.startswith('#') and '=' not in line:
                    break
    except Exception:
        pass
    
    return default_sep


def parse_account_line(line: str, separator: str) -> dict:
    """
    Parse account info line using specified separator.
    
    Args:
        line: Account info line
        separator: Field separator
        
    Returns:
        Parsed account dictionary
    """
    # NOTE: We do NOT strip inline comments here because # can appear in passwords
    # Lines that are pure comments (start with #) are already skipped in read_accounts()
    
    if not line:
        return None
    
    # Split using specified separator
    parts = line.split(separator)
    parts = [p.strip() for p in parts if p.strip()]
    
    if len(parts) < 2:
        return None
    
    result = {
        'email': '',
        'password': '',
        'backup_email': '',
        '2fa_secret': '',
        'full_line': line
    }
    
    # Assign fields in fixed order
    # Format: email [sep] password [sep] backup_email [sep] 2fa_secret
    if len(parts) >= 1:
        result['email'] = parts[0]
    if len(parts) >= 2:
        result['password'] = parts[1]
    if len(parts) >= 3:
        result['backup_email'] = parts[2]
    if len(parts) >= 4:
        result['2fa_secret'] = parts[3]
    
    return result if result['email'] else None


def read_accounts(file_path: str) -> list:
    """
    Read account info file (using configured separator).
    
    File format:
    First line (optional): separator="----"
    Following lines: email[sep]password[sep]backup_email[sep]2fa_secret
    
    Args:
        file_path: Path to accounts file
        
    Returns:
        List of account dictionaries
    """
    accounts = []
    
    if not os.path.exists(file_path):
        print(f"Error: File not found {file_path}")
        return accounts
    
    # Read separator config
    separator = read_separator_config(file_path)
    print(f"Using separator: '{separator}'")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Skip config lines
                if line.startswith('separator='):
                    continue
                
                account = parse_account_line(line, separator)
                if account:
                    accounts.append(account)
                else:
                    print(f"Warning: Line {line_num} format invalid: {line[:50]}")
    except Exception as e:
        print(f"Error reading file: {e}")
    
    return accounts


def get_browser_list(page: int = 0, pageSize: int = 50):
    """
    Get all browser windows list (using POST request with JSON body).
    
    Args:
        page: Page number, defaults to 0
        pageSize: Items per page, defaults to 50
    
    Returns:
        List of browser windows
    """
    try:
        json_data = {
            'page': page,
            'pageSize': pageSize
        }
        
        response = requests.post(
            f"{url}/browser/list",
            json=json_data,
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            res = response.json()
            if res.get('code') == 0 or res.get('success') == True:
                data = res.get('data', {})
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('list', [])
        return []
    except Exception:
        return []


def get_browser_info(browser_id: str):
    """
    Get detailed info for a specific browser window.
    
    Args:
        browser_id: Browser window ID
        
    Returns:
        Browser info dictionary
    """
    browsers = get_browser_list()
    for browser in browsers:
        if browser.get('id') == browser_id:
            return browser
    return None


def delete_browsers_by_name(name_pattern: str):
    """
    Delete all browser windows matching the name.
    
    Args:
        name_pattern: Window name (exact match)
        
    Returns:
        Number of deleted windows
    """
    browsers = get_browser_list()
    deleted_count = 0
    
    for browser in browsers:
        if browser.get('name') == name_pattern:
            browser_id = browser.get('id')
            try:
                res = requests.post(
                    f"{url}/browser/delete",
                    json={'id': browser_id},
                    headers=headers,
                    timeout=10
                ).json()
                
                if res.get('code') == 0 or res.get('success') == True:
                    deleted_count += 1
            except Exception:
                pass
    
    return deleted_count


def open_browser_by_id(browser_id: str):
    """
    Open a browser window by ID.
    
    Args:
        browser_id: Browser window ID
        
    Returns:
        bool: True if successful
    """
    try:
        res = requests.post(
            f"{url}/browser/open",
            json={'id': browser_id},
            headers=headers,
            timeout=30
        ).json()
        
        if res.get('code') == 0 or res.get('success') == True:
            return True
    except Exception:
        pass
    return False


def delete_browser_by_id(browser_id: str):
    """
    Delete a browser window by ID.
    
    Args:
        browser_id: Browser window ID
        
    Returns:
        bool: True if deletion successful
    """
    try:
        res = requests.post(
            f"{url}/browser/delete",
            json={'id': browser_id},
            headers=headers,
            timeout=10
        ).json()
        
        if res.get('code') == 0 or res.get('success') == True:
            return True
    except Exception:
        pass
    return False


def get_next_window_name(prefix: str):
    """
    Generate next window name based on prefix, format: prefix_number
    
    Args:
        prefix: Window name prefix
        
    Returns:
        Next window name, e.g. "USA_1"
    """
    browsers = get_browser_list()
    max_num = 0
    
    # Iterate all windows to find max number with matching prefix
    prefix_pattern = f"{prefix}_"
    for browser in browsers:
        name = browser.get('name', '')
        if name == prefix:
            # Exact match to prefix (treated as number 0 or 1)
            pass
              
        if name.startswith(prefix_pattern):
            try:
                # Extract suffix number
                suffix = name[len(prefix_pattern):]
                num = int(suffix)
                if num > max_num:
                    max_num = num
            except:
                pass
    
    return f"{prefix}_{max_num + 1}"


def open_browser_url(browser_id: str, target_url: str):
    """
    Open browser window and navigate to specified URL.
    
    Args:
        browser_id: Browser window ID
        target_url: URL to navigate to
    """
    try:
        res = requests.post(
            f"{url}/browser/open",
            json={"id": browser_id},
            headers=headers,
            timeout=30
        ).json()
        
        if res.get('code') == 0 or res.get('success') == True:
            driver_path = res.get('data', {}).get('driver')
            debugger_address = res.get('data', {}).get('http')
            
            if driver_path and debugger_address:
                try:
                    chrome_options = Options()
                    chrome_options.add_experimental_option("debuggerAddress", debugger_address)
                    chrome_service = Service(driver_path)
                    driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
                    driver.get(target_url)
                    time.sleep(2)
                    driver.quit()
                except Exception:
                    pass
    except Exception:
        pass


def create_browser_window(account: dict, reference_browser_id: str = None, proxy: dict = None, 
                          platform: str = None, extra_url: str = None, name_prefix: str = None, 
                          template_config: dict = None):
    """
    Create a new browser window/profile.
    
    Args:
        account: Account info dictionary
        reference_browser_id: Reference/template browser ID
        proxy: Proxy configuration
        platform: Platform URL
        extra_url: Additional URL
        name_prefix: Window name prefix
        template_config: Direct template config dict (takes priority over reference_browser_id)
        
    Returns:
        tuple: (browser_id, error_message)
    """
    if template_config:
        reference_config = template_config
    elif reference_browser_id:
        reference_config = get_browser_info(reference_browser_id)
        if not reference_config:
            return None, f"Reference window not found: {reference_browser_id}"
    else:
        return None, "No reference browser ID or template config specified"
    
    json_data = {}
    exclude_fields = {'id', 'name', 'remark', 'userName', 'password', 'faSecretKey', 'createTime', 'updateTime'}
    
    for key, value in reference_config.items():
        if key not in exclude_fields:
            json_data[key] = value
    
    # Determine window name
    if name_prefix:
        final_prefix = name_prefix
    else:
        # If no prefix specified, try to infer from reference window name
        ref_name = reference_config.get('name', '')
        if '_' in ref_name:
            final_prefix = '_'.join(ref_name.split('_')[:-1])
        else:
            final_prefix = ref_name
            
    json_data['name'] = get_next_window_name(final_prefix)
    json_data['remark'] = account['full_line']
    
    if platform:
        json_data['platform'] = platform
    if extra_url:
        json_data['url'] = extra_url
    
    if account.get('email'):
        json_data['userName'] = account['email']
    if account.get('password'):
        json_data['password'] = account['password']
    if account.get('2fa_secret') and account['2fa_secret'].strip():
        json_data['faSecretKey'] = account['2fa_secret'].strip()
    
    if 'browserFingerPrint' not in json_data:
        json_data['browserFingerPrint'] = {}
    
    if 'browserFingerPrint' in reference_config:
        ref_fp = reference_config['browserFingerPrint']
        if isinstance(ref_fp, dict):
            for key, value in ref_fp.items():
                if key != 'id':
                    json_data['browserFingerPrint'][key] = value
    
    json_data['browserFingerPrint']['coreVersion'] = '140'
    json_data['browserFingerPrint']['version'] = '140'
    
    if proxy:
        json_data['proxyType'] = proxy['type']
        json_data['proxyMethod'] = 2
        json_data['host'] = proxy['host']
        json_data['port'] = proxy['port']
        json_data['proxyUserName'] = proxy['username']
        json_data['proxyPassword'] = proxy['password']
    else:
        json_data['proxyType'] = 'noproxy'
        json_data['proxyMethod'] = 2
        json_data['host'] = ''
        json_data['port'] = ''
        json_data['proxyUserName'] = ''
        json_data['proxyPassword'] = ''
    
    
    # Check if window for this account already exists
    all_browsers = get_browser_list()
    for b in all_browsers:
        if b.get('userName') == account['email']:
            return None, f"Window for this account already exists: {b.get('name')} (ID: {b.get('id')})"

    try:
        res = requests.post(
            f"{url}/browser/update",
            json=json_data,
            headers=headers,
            timeout=10
        ).json()
        
        if res.get('code') == 0 or res.get('success') == True:
            browser_id = res.get('data', {}).get('id')
            if not browser_id:
                return None, "API returned success but no ID received"
            
            created_config = get_browser_info(browser_id)
            need_update = False
            if created_config:
                if created_config.get('userName') != account['email']:
                    need_update = True
                if created_config.get('password') != account['password']:
                    need_update = True
                if account.get('2fa_secret') and account['2fa_secret'].strip():
                    if created_config.get('faSecretKey') != account['2fa_secret'].strip():
                        need_update = True
            
            if need_update or 'userName' not in json_data:
                update_data = {
                    'ids': [browser_id],
                    'userName': account['email'],
                    'password': account['password']
                }
                
                if account.get('2fa_secret') and account['2fa_secret'].strip():
                    update_data['faSecretKey'] = account['2fa_secret'].strip()
                
                try:
                    update_res = requests.post(
                        f"{url}/browser/update/partial",
                        json=update_data,
                        headers=headers,
                        timeout=10
                    ).json()
                    
                    if not (update_res.get('code') == 0 or update_res.get('success') == True):
                        if 'faSecretKey' in update_data:
                            retry_data = {
                                'ids': [browser_id],
                                'userName': account['email'],
                                'password': account['password']
                            }
                            requests.post(
                                f"{url}/browser/update/partial",
                                json=retry_data,
                                headers=headers,
                                timeout=10
                            )
                except Exception:
                    pass
            
            if account.get('2fa_secret') and account['2fa_secret'].strip():
                verify_config = get_browser_info(browser_id)
                if not (verify_config and verify_config.get('faSecretKey') == account['2fa_secret'].strip()):
                    try:
                        twofa_data = {
                            'ids': [browser_id],
                            'faSecretKey': account['2fa_secret'].strip()
                        }
                        requests.post(
                            f"{url}/browser/update/partial",
                            json=twofa_data,
                            headers=headers,
                            timeout=10
                        )
                    except Exception:
                        pass
            
            return browser_id, None
        
        error_msg = res.get('msg', 'Unknown API error')
        return None, f"Create request rejected: {error_msg}"
        
    except Exception as e:
        return None, f"Request exception: {str(e)}"


def print_browser_info(browser_id: str):
    """Print complete config info for a browser window."""
    config = get_browser_info(browser_id)
    if config:
        print(json.dumps(config, indent=2, ensure_ascii=False))


def main():
    accounts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'accounts.txt')
    accounts = read_accounts(accounts_file)
    
    if not accounts:
        return
    
    proxies_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'proxies.txt')
    proxies = read_proxies(proxies_file)
    
    browsers = get_browser_list()
    if not browsers:
        return
    
    reference_browser_id = "4964d1fe7e584e868f14975f4c22e106"
    reference_config = get_browser_info(reference_browser_id)
    if not reference_config:
        browsers = get_browser_list()
        if browsers:
            reference_browser_id = browsers[0].get('id')
        else:
            return
    
    success_count = 0
    for i, account in enumerate(accounts, 1):
        proxy = proxies[i - 1] if i - 1 < len(proxies) else None
        browser_id, error = create_browser_window(account, reference_browser_id, proxy)
        if browser_id:
            success_count += 1
        else:
            print(f"Window creation failed: {error}")
        if i < len(accounts):
            time.sleep(1)
    
    print(f"Complete: {success_count}/{len(accounts)}")


if __name__ == "__main__":
    main()
