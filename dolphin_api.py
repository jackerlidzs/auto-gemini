"""
Dolphin Anty API Client

Local API for Dolphin Anty browser automation.
Compatible with Linux VPS deployment.

API Docs: https://dolphin-anty.com/docs/
Local API Port: 3001
"""
import requests
import json
import time
from typing import Optional, Dict, Any, Tuple

# Default local API URL
BASE_URL = "http://localhost:3001"

# Request headers
headers = {
    'Content-Type': 'application/json'
}


class DolphinAPI:
    """Dolphin Anty Local API Client"""
    
    def __init__(self, base_url: str = BASE_URL, api_token: str = None):
        """
        Initialize Dolphin Anty API client.
        
        Args:
            base_url: Local API URL (default: http://localhost:3001)
            api_token: Remote API token (optional, for remote operations)
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.headers = {'Content-Type': 'application/json'}
        if api_token:
            self.headers['Authorization'] = f'Bearer {api_token}'
    
    def check_connection(self) -> bool:
        """
        Check if Dolphin Anty local API is running.
        
        Returns:
            True if connected, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/v1.0/browser_profiles",
                headers=self.headers,
                timeout=5
            )
            return response.status_code in [200, 401]  # 401 means API is up but needs auth
        except Exception as e:
            print(f"Connection check failed: {e}")
            return False
    
    def get_profiles_list(self, page: int = 1, limit: int = 50) -> list:
        """
        Get list of browser profiles.
        
        Args:
            page: Page number (default: 1)
            limit: Items per page (default: 50)
            
        Returns:
            List of profile dictionaries
        """
        try:
            response = requests.get(
                f"{self.base_url}/v1.0/browser_profiles",
                params={'page': page, 'limit': limit},
                headers=self.headers,
                timeout=30
            )
            result = response.json()
            if result.get('success'):
                return result.get('data', [])
            return []
        except Exception as e:
            print(f"Failed to get profiles list: {e}")
            return []
    
    def get_profile_info(self, profile_id: str) -> Optional[Dict]:
        """
        Get profile information by ID.
        
        Args:
            profile_id: Profile ID
            
        Returns:
            Profile info dictionary or None
        """
        try:
            response = requests.get(
                f"{self.base_url}/v1.0/browser_profiles/{profile_id}",
                headers=self.headers,
                timeout=30
            )
            result = response.json()
            if result.get('success'):
                return result.get('data')
            return None
        except Exception as e:
            print(f"Failed to get profile info: {e}")
            return None
    
    def create_profile(
        self,
        name: str,
        proxy: Optional[Dict] = None,
        fingerprint: Optional[Dict] = None,
        notes: str = ""
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a new browser profile.
        
        Args:
            name: Profile name
            proxy: Proxy configuration dict {'type': 'http', 'host': '', 'port': '', 'login': '', 'password': ''}
            fingerprint: Custom fingerprint settings
            notes: Profile notes/remarks
            
        Returns:
            Tuple of (profile_id, error_message)
        """
        try:
            payload = {
                'name': name,
                'notes': notes,
                'platform': 'linux',
            }
            
            # Add proxy if provided
            if proxy:
                payload['proxy'] = {
                    'type': proxy.get('type', 'http'),
                    'host': proxy.get('host', ''),
                    'port': proxy.get('port', ''),
                    'login': proxy.get('username', ''),
                    'password': proxy.get('password', '')
                }
            
            # Add fingerprint if provided
            if fingerprint:
                payload['fingerprint'] = fingerprint
            
            response = requests.post(
                f"{self.base_url}/v1.0/browser_profiles",
                json=payload,
                headers=self.headers,
                timeout=60
            )
            result = response.json()
            
            if result.get('success'):
                profile_id = result.get('browserProfileId') or result.get('data', {}).get('id')
                return profile_id, None
            else:
                error = result.get('message') or result.get('error') or 'Unknown error'
                return None, error
                
        except Exception as e:
            return None, str(e)
    
    def open_browser(
        self,
        profile_id: str,
        headless: bool = False,
        automation: bool = True
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Open browser with specified profile.
        
        Args:
            profile_id: Profile ID to open
            headless: Run in headless mode (no GUI)
            automation: Enable automation mode (returns WebSocket endpoint)
            
        Returns:
            Tuple of (websocket_endpoint, error_message)
        """
        try:
            params = {}
            if automation:
                params['automation'] = '1'
            if headless:
                params['headless'] = '1'
            
            url = f"{self.base_url}/v1.0/browser_profiles/{profile_id}/start"
            
            print(f"Opening browser {profile_id}...")
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=120
            )
            result = response.json()
            
            if result.get('success'):
                data = result.get('automation', {})
                ws_endpoint = data.get('wsEndpoint') or data.get('ws')
                port = data.get('port')
                
                if ws_endpoint:
                    print(f"Browser opened. WebSocket: {ws_endpoint}")
                    return ws_endpoint, None
                elif port:
                    # Build WebSocket URL from port
                    ws_endpoint = f"ws://127.0.0.1:{port}/devtools/browser"
                    print(f"Browser opened. Port: {port}")
                    return ws_endpoint, None
                else:
                    return None, "No WebSocket endpoint in response"
            else:
                error = result.get('message') or result.get('error') or 'Failed to open browser'
                return None, error
                
        except Exception as e:
            return None, str(e)
    
    def close_browser(self, profile_id: str) -> bool:
        """
        Close browser with specified profile.
        
        Args:
            profile_id: Profile ID to close
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"Closing browser {profile_id}...")
            response = requests.get(
                f"{self.base_url}/v1.0/browser_profiles/{profile_id}/stop",
                headers=self.headers,
                timeout=30
            )
            result = response.json()
            success = result.get('success', False)
            if success:
                print("Browser closed successfully")
            return success
        except Exception as e:
            print(f"Failed to close browser: {e}")
            return False
    
    def delete_profile(self, profile_id: str) -> bool:
        """
        Delete browser profile.
        
        Args:
            profile_id: Profile ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.delete(
                f"{self.base_url}/v1.0/browser_profiles/{profile_id}",
                headers=self.headers,
                timeout=30
            )
            result = response.json()
            return result.get('success', False)
        except Exception as e:
            print(f"Failed to delete profile: {e}")
            return False
    
    def find_profile_by_name(self, name: str) -> Optional[str]:
        """
        Find profile ID by name.
        
        Args:
            name: Profile name to search
            
        Returns:
            Profile ID if found, None otherwise
        """
        profiles = self.get_profiles_list(limit=100)
        for profile in profiles:
            if profile.get('name') == name:
                return profile.get('id')
        return None
    
    def find_profile_by_notes(self, search_text: str) -> Optional[Dict]:
        """
        Find profile by notes/remarks content.
        
        Args:
            search_text: Text to search in notes
            
        Returns:
            Profile dict if found, None otherwise
        """
        profiles = self.get_profiles_list(limit=100)
        for profile in profiles:
            notes = profile.get('notes', '')
            if search_text in notes:
                return profile
        return None


# Singleton instance for easy import
_api_instance = None

def get_api(base_url: str = BASE_URL) -> DolphinAPI:
    """Get or create API instance"""
    global _api_instance
    if _api_instance is None:
        _api_instance = DolphinAPI(base_url)
    return _api_instance


# Convenience functions matching bit_api.py interface
def createBrowser(name: str, proxy: Dict = None, notes: str = "") -> Dict:
    """Create browser profile (BitBrowser compatible interface)"""
    api = get_api()
    profile_id, error = api.create_profile(name, proxy, notes=notes)
    if profile_id:
        return {'success': True, 'data': {'id': profile_id}}
    return {'success': False, 'msg': error}


def openBrowser(profile_id: str, headless: bool = False) -> Dict:
    """Open browser (BitBrowser compatible interface)"""
    api = get_api()
    ws_endpoint, error = api.open_browser(profile_id, headless=headless)
    if ws_endpoint:
        return {'success': True, 'data': {'ws': ws_endpoint}}
    return {'success': False, 'msg': error}


def closeBrowser(profile_id: str) -> Dict:
    """Close browser (BitBrowser compatible interface)"""
    api = get_api()
    success = api.close_browser(profile_id)
    return {'success': success}


def deleteBrowser(profile_id: str) -> Dict:
    """Delete browser profile (BitBrowser compatible interface)"""
    api = get_api()
    success = api.delete_profile(profile_id)
    return {'success': success}


def get_browser_list(page: int = 1, limit: int = 50) -> list:
    """Get browser profiles list (BitBrowser compatible interface)"""
    api = get_api()
    return api.get_profiles_list(page, limit)


def get_browser_info(profile_id: str) -> Optional[Dict]:
    """Get browser info (BitBrowser compatible interface)"""
    api = get_api()
    return api.get_profile_info(profile_id)


# Test script
if __name__ == '__main__':
    print("=" * 50)
    print("Dolphin Anty API Test")
    print("=" * 50)
    
    api = DolphinAPI()
    
    # Test connection
    print("\n[1] Testing connection...")
    if api.check_connection():
        print("✓ Connected to Dolphin Anty")
    else:
        print("✗ Failed to connect. Make sure Dolphin Anty is running.")
        exit(1)
    
    # Test list profiles
    print("\n[2] Listing profiles...")
    profiles = api.get_profiles_list()
    print(f"Found {len(profiles)} profiles")
    
    # Test create profile
    print("\n[3] Creating test profile...")
    profile_id, error = api.create_profile(
        name="AutoGemini_Test",
        notes="test@example.com----password----backup"
    )
    if profile_id:
        print(f"✓ Created profile: {profile_id}")
        
        # Test open browser
        print("\n[4] Opening browser...")
        ws, error = api.open_browser(profile_id, headless=True)
        if ws:
            print(f"✓ Browser opened: {ws}")
            
            # Wait a bit
            print("Waiting 3 seconds...")
            time.sleep(3)
            
            # Close browser
            print("\n[5] Closing browser...")
            api.close_browser(profile_id)
        else:
            print(f"✗ Failed to open: {error}")
        
        # Delete profile
        print("\n[6] Deleting test profile...")
        api.delete_profile(profile_id)
        print("✓ Profile deleted")
    else:
        print(f"✗ Failed to create profile: {error}")
    
    print("\n" + "=" * 50)
    print("Test completed!")
