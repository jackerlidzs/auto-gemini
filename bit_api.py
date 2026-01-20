"""
BitBrowser Local API Client

Official Documentation: https://doc2.bitbrowser.cn/jiekou/ben-di-fu-wu-zhi-nan.html

This module provides functions to interact with BitBrowser's local API service.
The fingerprint parameters used here are minimal examples - refer to docs for full options.
"""
import requests
import json
import time

# BitBrowser local API endpoint
url = "http://127.0.0.1:54345"
headers = {
    'Content-Type': 'application/json',
    'x-api-key': '91d1df9772a24f7ba67646c327727086'  # BitBrowser API Token
}


def createBrowser():
    """
    Create a new browser window/profile.
    
    If no specific fingerprint requirements, just specify the core version.
    For detailed fingerprint parameters, refer to the official documentation.
    
    Returns:
        str: The browser ID of the newly created window
    """
    json_data = {
        'name': 'google',  # Window name
        'remark': '',  # Remark/notes
        'proxyMethod': 2,  # Proxy method: 2=custom, 3=extract IP
        # Proxy type options: ['noproxy', 'http', 'https', 'socks5', 'ssh']
        'proxyType': 'noproxy',
        'host': '',  # Proxy host
        'port': '',  # Proxy port
        'proxyUserName': '',  # Proxy username
        "browserFingerPrint": {  # Fingerprint configuration
            # Core version. Note: Win7/Win8/WinServer2012 don't support v112+
            'coreVersion': '124'
        }
    }

    print("Creating browser window...")
    res = requests.post(
        f"{url}/browser/update",
        json=json_data,
        headers=headers,
        timeout=10  # 10 second timeout
    ).json()
    browserId = res['data']['id']
    print(f"Window created successfully, ID: {browserId}")
    return browserId


def updateBrowser():
    """
    Update browser window(s).
    
    Supports batch updates and partial updates.
    Pass IDs as an array - for single update, just pass one ID.
    Only include fields that need to be modified.
    If browserFingerPrint doesn't need changes, don't include it.
    """
    json_data = {
        'ids': ['93672cf112a044f08b653cab691216f0'],
        'remark': 'This is a remark',
        'browserFingerPrint': {}
    }
    res = requests.post(
        f"{url}/browser/update/partial",
        json=json_data,
        headers=headers
    ).json()
    print(res)


def openBrowser(id):
    """
    Open a browser window by ID.
    
    Args:
        id: Browser window ID (can use ID returned from createBrowser)
    
    Returns:
        dict: Response containing WebSocket endpoint and other info
    """
    json_data = {"id": f'{id}'}
    print(f"Opening window {id}...")
    res = requests.post(
        f"{url}/browser/open",
        json=json_data,
        headers=headers,
        timeout=30  # 30 second timeout
    ).json()
    print(f"Window open response: {res}")
    return res


def closeBrowser(id):
    """
    Close a browser window by ID.
    
    Args:
        id: Browser window ID to close
    """
    json_data = {'id': f'{id}'}
    print(f"Closing window {id}...")
    res = requests.post(
        f"{url}/browser/close",
        json=json_data,
        headers=headers,
        timeout=10  # 10 second timeout
    ).json()
    print(f"Window close response: {res}")


def deleteBrowser(id):
    """
    Delete a browser window/profile by ID.
    
    Args:
        id: Browser window ID to delete
    """
    json_data = {'id': f'{id}'}
    print(f"Deleting window {id}...")
    res = requests.post(
        f"{url}/browser/delete",
        json=json_data,
        headers=headers,
        timeout=10  # 10 second timeout
    ).json()
    print(f"Window delete response: {res}")


if __name__ == '__main__':
    try:
        browser_id = createBrowser()
        openBrowser(browser_id)

        print("\nWaiting 10 seconds before auto-closing window...")
        time.sleep(10)  # Wait 10 seconds then auto-close

        closeBrowser(browser_id)

        print("\nWaiting 10 seconds before auto-deleting window...")
        time.sleep(10)  # Wait 10 seconds then auto-delete

        deleteBrowser(browser_id)
        print("\nProgram execution completed!")
    except requests.exceptions.Timeout:
        print("\n[ERROR] Request timed out. Please check if BitBrowser service is running.")
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Cannot connect to BitBrowser API. Please ensure BitBrowser is running.")
    except Exception as e:
        print(f"\n[ERROR] Exception occurred: {e}")
        import traceback
        traceback.print_exc()
