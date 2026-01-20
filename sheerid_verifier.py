"""
SheerID Batch Verifier

API client for batch.1key.me SheerID verification service.
Handles CSRF token management, batch verification, and status polling.
"""
import requests
import re
import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://batch.1key.me"
DEFAULT_API_KEY = "cdk_+KY2F:64M_4x%Hn-o0*+mqtJOgf*qaoc"  # SheerID API key


class SheerIDVerifier:
    """
    Client for batch.1key.me SheerID verification API.
    
    Attributes:
        session: Requests session for connection persistence
        api_key: API key for captcha bypass (hCaptchaToken)
        csrf_token: CSRF token for API authentication
    """
    
    def __init__(self, api_key=DEFAULT_API_KEY):
        """
        Initialize SheerID verifier.
        
        Args:
            api_key: API key for hCaptcha bypass. Required for automated verification.
        """
        self.session = requests.Session()
        self.api_key = api_key
        self.csrf_token = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/"
        }

    def _get_csrf_token(self):
        """
        Fetch homepage and extract CSRF token.
        
        Returns:
            bool: True if token obtained successfully, False otherwise
        """
        try:
            logger.info("Fetching CSRF token...")
            resp = self.session.get(BASE_URL, headers=self.headers, timeout=10)
            resp.raise_for_status()
            
            logger.debug(f"Response status: {resp.status_code}")
            logger.debug(f"Response length: {len(resp.text)} chars")
            
            # Try multiple CSRF token patterns
            patterns = [
                r'window\.CSRF_TOKEN\s*=\s*["\']([^"\']+)["\']',  # window.CSRF_TOKEN = "..."
                r'csrfToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',  # csrfToken: "..." or csrfToken = "..."
                r'_csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']',      # _csrf: "..." or _csrf = "..."
            ]
            
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, resp.text, re.IGNORECASE)
                if match:
                    self.csrf_token = match.group(1)
                    self.headers["X-CSRF-Token"] = self.csrf_token
                    logger.info(f"[OK] CSRF Token obtained (pattern {i+1}): {self.csrf_token[:10]}...")
                    return True
            
            # If no patterns matched, output debug info
            logger.error("[FAIL] CSRF Token pattern not found in page.")
            logger.error(f"Page content preview (first 1000 chars):\n{resp.text[:1000]}")
            
            # Look for potential token-related strings
            token_hints = re.findall(r'(csrf|token|_token)[^"\']*["\']([^"\']{20,})["\']', resp.text, re.IGNORECASE)
            if token_hints:
                logger.info(f"Found potential token patterns: {token_hints[:3]}")
            
            # Attempt to proceed without CSRF token
            logger.warning("Attempting to proceed without CSRF token...")
            return False
            
        except Exception as e:
            logger.error(f"Failed to get CSRF token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def verify_batch(self, verification_ids, callback=None):
        """
        Verify a batch of SheerID verification IDs.
        
        Args:
            verification_ids: List of verification ID strings
            callback: Optional callback function(vid, message) for progress updates
            
        Returns:
            dict: {verification_id: status_result} mapping
        """
        # Refresh CSRF token before each batch to ensure validity
        logger.info("Refreshing CSRF token before batch...")
        if not self._get_csrf_token():
            logger.warning("CSRF token refresh failed, attempting with old/no token")

        results = {}
        # Max 5 IDs per batch if API key is present
        # API requires hCaptchaToken to be the API Key for bypass
        
        payload = {
            "verificationIds": verification_ids,
            "hCaptchaToken": self.api_key, 
            "useLucky": False,
            "programId": ""
        }
        
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"

        try:
            logger.info(f"Submitting batch verification for {len(verification_ids)} IDs...")
            logger.info(f"[KEY] API Key: {self.api_key[:10] if self.api_key else '[EMPTY]'}...")
            logger.info(f"[PAYLOAD] verificationIds={verification_ids}, hCaptchaToken={self.api_key[:10] if self.api_key else 'NONE'}...")
            
            resp = self.session.post(
                f"{BASE_URL}/api/batch", 
                headers=headers, 
                json=payload,
                stream=True,
                timeout=30
            )
            
            # If 403/401 returned, token expired - try again
            if resp.status_code in [403, 401]:
                logger.warning(f"Token expired (status {resp.status_code}), refreshing again...")
                if self._get_csrf_token():
                    headers["X-CSRF-Token"] = self.csrf_token
                    resp = self.session.post(
                        f"{BASE_URL}/api/batch", 
                        headers=headers, 
                        json=payload,
                        stream=True,
                        timeout=30
                    )
                else:
                    return {vid: {"status": "error", "message": "Token expired and refresh failed"} for vid in verification_ids}

            # Check response status
            if resp.status_code != 200:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.error(f"Batch request failed: {error_msg}")
                return {vid: {"status": "error", "message": error_msg} for vid in verification_ids}

            # Parse SSE Stream
            # The API returns "data: {...json...}" lines
            for line in resp.iter_lines():
                if not line:
                    continue
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data:"):
                    json_str = decoded_line[5:].strip()
                    try:
                        data = json.loads(json_str)
                        self._handle_api_response(data, results, callback)
                    except json.JSONDecodeError:
                        pass
                        
        except Exception as e:
            logger.error(f"Batch verify request failed: {e}")
            for vid in verification_ids:
                if vid not in results:
                    results[vid] = {"status": "error", "message": str(e)}

        return results

    def _handle_api_response(self, data, results, callback=None):
        """
        Handle individual data chunks from SSE or poll response.
        
        Args:
            data: Parsed JSON data from API
            results: Results dictionary to update
            callback: Optional progress callback
        """
        vid = data.get("verificationId")
        if not vid:
            return

        status = data.get("currentStep")
        message = data.get("message", "")
        
        if callback:
            callback(vid, f"Step: {status} | Msg: {message}")

        if status == "pending" and "checkToken" in data:
            # Need to poll for completion
            check_token = data["checkToken"]
            final_res = self._poll_status(check_token, vid, callback)
            results[vid] = final_res
        elif status == "success" or status == "error":
            # Done
            results[vid] = data

    def _poll_status(self, check_token, vid, callback=None):
        """
        Poll /api/check-status until success or error.
        
        Args:
            check_token: Token for status check
            vid: Verification ID
            callback: Optional progress callback
            
        Returns:
            dict: Final status result
        """
        url = f"{BASE_URL}/api/check-status"
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        
        # Poll max 60 times (approx 120s)
        for i in range(60):
            try:
                time.sleep(2)  # Wait 2s between polls
                payload = {"checkToken": check_token}
                
                # Increased timeout to 30s to handle slow networks
                resp = self.session.post(url, headers=headers, json=payload, timeout=30)
                json_data = resp.json()
                
                status = json_data.get("currentStep")
                message = json_data.get("message", "")
                
                if callback:
                    callback(vid, f"Polling: {status} ({i+1}/60) | Msg: {message}")

                if status == "success" or status == "error":
                    return json_data
                
                # If pending, update checkToken if provided
                if "checkToken" in json_data:
                    check_token = json_data["checkToken"]
                    
            except requests.exceptions.Timeout as e:
                # Network timeout, continue retrying
                logger.warning(f"Polling timeout (attempt {i+1}/60), retrying...")
                if callback:
                    callback(vid, f"Polling: timeout (retrying {i+1}/60)")
                continue
                
            except Exception as e:
                logger.error(f"Polling failed: {e}")
                # Other errors, also continue retrying instead of failing immediately
                if callback:
                    callback(vid, f"Polling error: {str(e)[:50]} (retrying {i+1}/60)")
                continue
        
        return {"status": "error", "message": "Polling timeout (120s)"}

    def cancel_verification(self, verification_id):
        """
        Cancel a verification process.
        
        Args:
            verification_id: ID of verification to cancel
            
        Returns:
            dict: API response
        """
        if not self.csrf_token:
            if not self._get_csrf_token():
                return {"status": "error", "message": "No CSRF Token"}
        
        url = f"{BASE_URL}/api/cancel"
        headers = self.headers.copy()
        headers["X-CSRF-Token"] = self.csrf_token
        headers["Content-Type"] = "application/json"
        
        try:
            resp = self.session.post(url, headers=headers, json={"verificationId": verification_id}, timeout=10)
            try:
                return resp.json()
            except:
                return {"status": "error", "message": f"Invalid JSON: {resp.text}"}
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    pass
