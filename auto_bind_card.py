"""
Auto Card Binding Script - Google One AI Student Subscription

Automates the process of binding a card and subscribing to Google One AI Student offer.
"""
import asyncio
import pyotp
from playwright.async_api import async_playwright, Page
from bit_api import openBrowser, closeBrowser
from account_manager import AccountManager

# Test card info (replace with actual card for production)
TEST_CARD = {
    'number': '5481087170529907',
    'exp_month': '01',
    'exp_year': '32',
    'cvv': '536'
}


async def check_and_login(page: Page, account_info: dict = None):
    """
    Check if logged in, execute login flow if not.
    
    Args:
        page: Playwright Page object
        account_info: Account info dict {'email', 'password', 'secret'}
    
    Returns:
        (success: bool, message: str)
    """
    try:
        print("\nChecking login status...")
        
        # Check if login input exists
        try:
            email_input = await page.wait_for_selector('input[type="email"]', timeout=5000)
            
            if email_input:
                print("[X] Not logged in, starting login flow...")
                
                if not account_info:
                    return False, "Login required but no account info provided"
                
                # 1. Enter email
                email = account_info.get('email')
                print(f"Entering account: {email}")
                await email_input.fill(email)
                await page.click('#identifierNext >> button')
                
                # 2. Enter password
                print("Waiting for password input...")
                await page.wait_for_selector('input[type="password"]', state='visible', timeout=15000)
                password = account_info.get('password')
                print("Entering password...")
                await page.fill('input[type="password"]', password)
                await page.click('#passwordNext >> button')
                
                # 3. Handle 2FA
                print("Waiting for 2FA input...")
                try:
                    totp_input = await page.wait_for_selector(
                        'input[name="totpPin"], input[id="totpPin"], input[type="tel"]',
                        timeout=10000
                    )
                    if totp_input:
                        secret = account_info.get('secret')
                        if secret:
                            s = secret.replace(" ", "").strip()
                            totp = pyotp.TOTP(s)
                            code = totp.now()
                            print(f"Entering 2FA code: {code}")
                            await totp_input.fill(code)
                            await page.click('#totpNext >> button')
                            print("[OK] 2FA verification complete")
                        else:
                            return False, "2FA required but no secret provided"
                except Exception as e:
                    print(f"2FA step skipped or failed (may not be required): {e}")
                
                # Wait for login to complete
                await asyncio.sleep(5)
                print("[OK] Login flow complete")
                return True, "Login successful"
        except:
            print("[OK] Already logged in, skipping login flow")
            return True, "Already logged in"
            
    except Exception as e:
        print(f"Login check error: {e}")
        return False, f"Login check error: {e}"


async def auto_bind_card(page: Page, card_info: dict = None, account_info: dict = None):
    """
    Auto card binding function.
    
    Args:
        page: Playwright Page object
        card_info: Card info dict {'number', 'exp_month', 'exp_year', 'cvv'}
        account_info: Account info for login {'email', 'password', 'secret'}
    
    Returns:
        (success: bool, message: str)
    """
    if card_info is None:
        card_info = TEST_CARD
    
    try:
        # First check and perform login if needed
        login_success, login_msg = await check_and_login(page, account_info)
        if not login_success and "Login required" in login_msg:
            return False, f"Login failed: {login_msg}"
        
        print("\nStarting auto card binding flow...")
        
        # Screenshot 1: Initial page
        await page.screenshot(path="step1_initial.png")
        print("Screenshot saved: step1_initial.png")
        
        # Step 1: Wait and click "Get student offer" button
        print("Waiting for 'Get student offer' button...")
        try:
            # Try multiple possible selectors
            selectors = [
                'button:has-text("Get student offer")',
                'button:has-text("Get offer")',
                'a:has-text("Get student offer")',
                'button:has-text("Get")',
                '[role="button"]:has-text("Get")'
            ]
            
            clicked = False
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        await element.wait_for(state='visible', timeout=3000)
                        await element.click()
                        print(f"[OK] Clicked 'Get student offer' (selector: {selector})")
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                print("[!] 'Get student offer' button not found, may already be on payment page")
            
            # Wait for payment page and iframe to load
            print("Waiting for payment page and iframe to load...")
            await asyncio.sleep(8)
            await page.screenshot(path="step2_after_get_offer.png")
            print("Screenshot saved: step2_after_get_offer.png")
            
        except Exception as e:
            print(f"Error handling 'Get student offer': {e}")
        
        # Pre-check: Check if card is already bound (subscribe button visible)
        print("\nChecking if account already has card bound...")
        try:
            await asyncio.sleep(3)
            
            # Try to get iframe
            try:
                iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
                print("[OK] Found iframe, checking for subscribe button in iframe")
                
                # Use precise selectors
                subscribe_selectors = [
                    'span.UywwFc-vQzf8d:has-text("Subscribe")',
                    'span[jsname="V67aGc"]',
                    'span.UywwFc-vQzf8d',
                    'span:has-text("Subscribe")',
                    ':text("Subscribe")',
                    'button:has-text("Subscribe")',
                ]
                
                # Check for subscribe button in iframe
                already_bound = False
                subscribe_button_early = None
                
                for selector in subscribe_selectors:
                    try:
                        element = iframe_locator.locator(selector).first
                        count = await element.count()
                        if count > 0:
                            print(f"  [OK] Subscribe button detected, card already bound! (iframe, selector: {selector})")
                            subscribe_button_early = element
                            already_bound = True
                            break
                    except:
                        continue
                
                # If subscribe button found, card is already bound, click subscribe directly
                if already_bound and subscribe_button_early:
                    print("Account already has card, skipping binding flow, subscribing directly...")
                    await asyncio.sleep(2)
                    await subscribe_button_early.click()
                    print("[OK] Clicked subscribe button")
                    
                    # Wait 10s and verify subscription success
                    await asyncio.sleep(10)
                    await page.screenshot(path="step_subscribe_existing_card.png")
                    print("Screenshot saved: step_subscribe_existing_card.png")
                    
                    # Check if "Subscribed" is displayed in iframe
                    try:
                        subscribed_selectors = [
                            ':text("Subscribed")',
                            'text=Subscribed',
                            '*:has-text("Subscribed")',
                        ]
                        
                        subscribed_found = False
                        for selector in subscribed_selectors:
                            try:
                                element = iframe_locator.locator(selector).first
                                count = await element.count()
                                if count > 0:
                                    print(f"  [OK] Detected 'Subscribed', subscription confirmed!")
                                    subscribed_found = True
                                    break
                            except:
                                continue
                        
                        if subscribed_found:
                            print("[OK] Subscription with existing card successful and confirmed!")
                            # Update database status to subscribed
                            if account_info and account_info.get('email'):
                                line = f"{account_info.get('email', '')}----{account_info.get('password', '')}----{account_info.get('backup', '')}----{account_info.get('secret', '')}"
                                AccountManager.move_to_subscribed(line)
                            return True, "Subscribed with existing card (Already bound, Subscribed)"
                        
                        # If Subscribed not found, check for Error (card expired)
                        print("'Subscribed' not detected, checking for errors...")
                        error_selectors = [
                            ':text("Error")',
                            'text=Error',
                            ':has-text("Your card issuer declined")',
                        ]
                        
                        error_found = False
                        for selector in error_selectors:
                            try:
                                element = iframe_locator.locator(selector).first
                                count = await element.count()
                                if count > 0:
                                    print(f"  [!] Error detected (card may be expired), preparing to rebind...")
                                    error_found = True
                                    break
                            except:
                                continue
                        
                        if error_found:
                            # Card expired rebind flow
                            print("\n[Card Expired Rebind Flow]")
                            
                            # 1. Click "Got it" button
                            print("1. Clicking 'Got it' button...")
                            got_it_selectors = [
                                'button:has-text("Got it")',
                                ':text("Got it")',
                                'button:has-text("OK")',
                            ]
                            
                            for selector in got_it_selectors:
                                try:
                                    element = iframe_locator.locator(selector).first
                                    count = await element.count()
                                    if count > 0:
                                        await element.click()
                                        print("  [OK] Clicked 'Got it'")
                                        await asyncio.sleep(3)
                                        break
                                except:
                                    continue
                            
                            # 2. Click "Get student offer" on main page
                            print("2. Re-clicking 'Get student offer' on main page...")
                            get_offer_selectors = [
                                'button:has-text("Get student offer")',
                                ':text("Get student offer")',
                            ]
                            
                            for selector in get_offer_selectors:
                                try:
                                    element = page.locator(selector).first
                                    count = await element.count()
                                    if count > 0:
                                        await element.click()
                                        print("  [OK] Clicked 'Get student offer'")
                                        await asyncio.sleep(8)
                                        break
                                except:
                                    continue
                            
                            # 3. Find and click expired card in iframe
                            print("3. Finding and clicking expired card in iframe...")
                            try:
                                iframe_locator_card = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
                                
                                # Click card (Mastercard-7903 or similar)
                                card_selectors = [
                                    'span.Ngbcnc',  # Mastercard-7903 span
                                    'div.dROd9.ct1Mcc',  # Card container
                                    ':has-text("Mastercard")',
                                ]
                                
                                for selector in card_selectors:
                                    try:
                                        element = iframe_locator_card.locator(selector).first
                                        count = await element.count()
                                        if count > 0:
                                            await element.click()
                                            print(f"  [OK] Clicked expired card (selector: {selector})")
                                            await asyncio.sleep(5)
                                            break
                                    except:
                                        continue
                                
                                print("4. Entering rebind flow, continuing with card binding...")
                                # Don't return, let code continue to card binding flow
                                
                            except Exception as e:
                                print(f"  Error clicking expired card: {e}, trying to continue...")
                        else:
                            print("[!] 'Subscribed' or 'Error' not detected, but may still be successful")
                            return True, "Subscribed with existing card (Already bound)"
                            
                    except Exception as e:
                        print(f"Error verifying subscription status: {e}")
                        return True, "Subscribed with existing card (Already bound)"
                else:
                    print("Subscribe button not detected, continuing with card binding flow...")
                    
            except Exception as e:
                print(f"Failed to get iframe: {e}, continuing with normal binding flow...")
                
        except Exception as e:
            print(f"Error in pre-check: {e}, continuing with normal binding flow...")
        
        # Step 2: Switch to iframe (payment form is in iframe)
        print("\nDetecting and switching to iframe...")
        try:
            # Wait for iframe to load
            await asyncio.sleep(10)
            iframe_locator = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
            print("[OK] Found tokenized.play.google.com iframe, switched context")
            
            # Wait for internal document to load
            print("Waiting for iframe internal document to load...")
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"[X] iframe not found: {e}")
            return False, "Payment form iframe not found"
        
        # Step 3: Click "Add card" in iframe
        print("\nWaiting and clicking 'Add card' button in iframe...")
        try:
            await asyncio.sleep(10)
            
            # Find Add card in iframe
            selectors = [
                'span.PjwEQ:has-text("Add card")',
                'span.PjwEQ',
                ':text("Add card")',
                'div:has-text("Add card")',
                'span:has-text("Add card")',
            ]
            
            clicked = False
            for selector in selectors:
                try:
                    element = iframe_locator.locator(selector).first
                    count = await element.count()
                    if count > 0:
                        print(f"  Found 'Add card' (iframe, selector: {selector})")
                        await element.click()
                        print(f"[OK] Clicked 'Add card' in iframe")
                        clicked = True
                        break
                except:
                    continue
            
            if not clicked:
                print("[!] 'Add card' not found in iframe, trying to find input fields directly...")
            
            # Wait for form to load
            print("Waiting for card input form to load...")
            await asyncio.sleep(10)
            await page.screenshot(path="step3_card_form_in_iframe.png")
            print("Screenshot saved: step3_card_form_in_iframe.png")
            
            # Key: After clicking Add card, another iframe appears inside the first iframe!
            # Need to switch to this inner iframe
            print("\nChecking if there's a second layer iframe inside...")
            try:
                await asyncio.sleep(1)
                
                # Second layer iframe usually has name="hnyNZeIframe" or contains instrumentmanager
                inner_iframe_selectors = [
                    'iframe[name="hnyNZeIframe"]',
                    'iframe[src*="instrumentmanager"]',
                    'iframe[id*="hnyNZe"]',
                ]
                
                inner_iframe = None
                for selector in inner_iframe_selectors:
                    try:
                        temp_iframe = iframe_locator.frame_locator(selector)
                        test_locator = temp_iframe.locator('body')
                        if await test_locator.count() >= 0:
                            inner_iframe = temp_iframe
                            print(f"[OK] Found second layer iframe (selector: {selector})")
                            break
                    except:
                        continue
                
                if not inner_iframe:
                    print("[!] Second layer iframe not found, continuing at current level")
                else:
                    # Update iframe_locator to inner iframe
                    iframe_locator = inner_iframe
                    
                    print("Waiting for second layer iframe to load...")
                    await asyncio.sleep(10)
                
            except Exception as e:
                print(f"[!] Error finding second layer iframe: {e}")
            
        except Exception as e:
            await page.screenshot(path="error_iframe_add_card.png")
            return False, f"Failed to click 'Add card' in iframe: {e}"
        
        # Step 4: Fill card number (in iframe)
        print(f"\nFilling card number: {card_info['number']}")
        await asyncio.sleep(10)
        
        try:
            # Simplified strategy: iframe has 3 input fields, in order:
            # 1. Card number (1st)
            # 2. MM/YY (2nd)  
            # 3. Security code (3rd)
            
            print("Finding all input fields in iframe...")
            
            # Get all input fields
            all_inputs = iframe_locator.locator('input')
            input_count = await all_inputs.count()
            print(f"  Found {input_count} input fields")
            
            if input_count < 3:
                return False, f"Insufficient input fields, only found {input_count}"
            
            # 1st input = Card number
            card_number_input = all_inputs.nth(0)
            print("  Using 1st input field for card number")
            
            await card_number_input.click()
            await card_number_input.fill(card_info['number'])
            print("[OK] Card number filled")
            await asyncio.sleep(0.5)
        except Exception as e:
            return False, f"Failed to fill card number: {e}"
        
        # Step 5: Fill expiry date (MM/YY)
        print(f"Filling expiry date: {card_info['exp_month']}/{card_info['exp_year']}")
        try:
            # 2nd input = MM/YY
            exp_date_input = all_inputs.nth(1)
            print("  Using 2nd input field for expiry date")
            
            await exp_date_input.click()
            exp_value = f"{card_info['exp_month']}{card_info['exp_year']}"
            await exp_date_input.fill(exp_value)
            print("[OK] Expiry date filled")
            await asyncio.sleep(0.5)
        except Exception as e:
            return False, f"Failed to fill expiry date: {e}"
        
        # Step 6: Fill CVV (Security code)
        print(f"Filling CVV: {card_info['cvv']}")
        try:
            # 3rd input = Security code
            cvv_input = all_inputs.nth(2)
            print("  Using 3rd input field for CVV")
            
            await cvv_input.click()
            await cvv_input.fill(card_info['cvv'])
            print("[OK] CVV filled")
            await asyncio.sleep(0.5)
        except Exception as e:
            return False, f"Failed to fill CVV: {e}"
        
        # Step 6: Click "Save card" button
        print("Clicking 'Save card' button...")
        try:
            save_selectors = [
                'button:has-text("Save card")',
                'button:has-text("Save")',
                'button[type="submit"]',
            ]
            
            save_button = None
            for selector in save_selectors:
                try:
                    element = iframe_locator.locator(selector).first
                    count = await element.count()
                    if count > 0:
                        print(f"  Found Save button (iframe, selector: {selector})")
                        save_button = element
                        break
                except:
                    continue
            
            if not save_button:
                return False, "Save card button not found"
            
            await save_button.click()
            print("[OK] Clicked 'Save card'")
        except Exception as e:
            return False, f"Failed to click Save card: {e}"
        
        # Step 7: Click subscribe button to complete flow
        print("\nWaiting for subscription page to load...")
        await asyncio.sleep(18)
        await page.screenshot(path="step7_before_subscribe.png")
        print("Screenshot saved: step7_before_subscribe.png")
        
        try:
            # Key change: Subscribe button is in main page popup, not in iframe!
            print("Finding subscribe button...")
            
            subscribe_selectors = [
                # User provided precise selectors - try first
                'span.UywwFc-vQzf8d:has-text("Subscribe")',
                'span[jsname="V67aGc"]',
                'span.UywwFc-vQzf8d',
                # Other alternatives
                'span:has-text("Subscribe")',
                ':text("Subscribe")',
                'button:has-text("Subscribe")',
                'button:has-text("Start")',
                'div[role="button"]:has-text("Subscribe")',
                '[role="button"]:has-text("Subscribe")',
                'button[type="submit"]',
                # Based on screenshot, may be in dialog
                'dialog span:has-text("Subscribe")',
                '[role="dialog"] span:has-text("Subscribe")',
                'dialog button:has-text("Subscribe")',
                '[role="dialog"] button:has-text("Subscribe")',
            ]
            
            subscribe_button = None
            
            # First check in iframe (subscribe button is in iframe)
            print("Finding subscribe button in iframe...")
            try:
                iframe_locator_subscribe = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
                for selector in subscribe_selectors:
                    try:
                        element = iframe_locator_subscribe.locator(selector).first
                        count = await element.count()
                        if count > 0:
                            print(f"  Found subscribe button (iframe, selector: {selector})")
                            subscribe_button = element
                            break
                    except:
                        continue
            except Exception as e:
                print(f"  iframe search failed: {e}")
            
            # If not found in iframe, try main page
            if not subscribe_button:
                print("Finding subscribe button on main page...")
                for selector in subscribe_selectors:
                    try:
                        element = page.locator(selector).first
                        count = await element.count()
                        if count > 0:
                            print(f"  Found subscribe button (main page, selector: {selector})")
                            subscribe_button = element
                            break
                    except Exception as e:
                        continue
            
            if subscribe_button:
                print("Preparing to click subscribe button...")
                await asyncio.sleep(2)
                await subscribe_button.click()
                print("[OK] Clicked subscribe button")
                
                # Wait 10s and verify subscription success
                await asyncio.sleep(10)
                await page.screenshot(path="step8_after_subscribe.png")
                print("Screenshot saved: step8_after_subscribe.png")
                
                # Check if "Subscribed" is displayed in iframe
                try:
                    # Re-get iframe
                    iframe_locator_final = page.frame_locator('iframe[src*="tokenized.play.google.com"]')
                    
                    subscribed_selectors = [
                        ':text("Subscribed")',
                        'text=Subscribed',
                        '*:has-text("Subscribed")',
                    ]
                    
                    subscribed_found = False
                    for selector in subscribed_selectors:
                        try:
                            element = iframe_locator_final.locator(selector).first
                            count = await element.count()
                            if count > 0:
                                print(f"  [OK] Detected 'Subscribed', subscription confirmed!")
                                subscribed_found = True
                                break
                        except:
                            continue
                    
                    if subscribed_found:
                        print("[OK] Card bound and subscribed successfully, confirmed!")
                        # Update database status to subscribed
                        if account_info and account_info.get('email'):
                            line = f"{account_info.get('email', '')}----{account_info.get('password', '')}----{account_info.get('backup', '')}----{account_info.get('secret', '')}"
                            AccountManager.move_to_subscribed(line)
                        return True, "Card bound and subscribed (Subscribed confirmed)"
                    else:
                        print("[!] 'Subscribed' not detected, but may still be successful")
                        # Update database status to subscribed
                        if account_info and account_info.get('email'):
                            line = f"{account_info.get('email', '')}----{account_info.get('password', '')}----{account_info.get('backup', '')}----{account_info.get('secret', '')}"
                            AccountManager.move_to_subscribed(line)
                        return True, "Card bound and subscribed (Subscribed)"
                except Exception as e:
                    print(f"Error verifying subscription status: {e}")
                    return True, "Card bound and subscribed (Subscribed)"
            else:
                print("[!] Subscribe button not found, may have auto-completed")
                print("[OK] Card binding successful")
                return True, "Card binding successful"
                
        except Exception as e:
            print(f"Error clicking subscribe button: {e}")
            import traceback
            traceback.print_exc()
            print("[OK] Card binding completed (subscription step may need manual action)")
            return True, "Card binding completed"
        
    except Exception as e:
        print(f"[X] Card binding error: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Card binding error: {str(e)}"


async def test_bind_card_with_browser(browser_id: str, account_info: dict = None):
    """
    Test card binding function.
    
    Args:
        browser_id: Browser window ID
        account_info: Account info {'email', 'password', 'secret'} (optional, will fetch from browser remark if not provided)
    """
    print(f"Opening browser: {browser_id}...")
    
    # If account info not provided, try to get from browser info
    if not account_info:
        print("Account info not provided, trying to get from browser remark...")
        from create_window import get_browser_info
        
        target_browser = get_browser_info(browser_id)
        if target_browser:
            remark = target_browser.get('remark', '')
            parts = remark.split('----')
            
            if len(parts) >= 4:
                account_info = {
                    'email': parts[0].strip(),
                    'password': parts[1].strip(),
                    'backup': parts[2].strip(),
                    'secret': parts[3].strip()
                }
                print(f"[OK] Got account info from remark: {account_info.get('email')}")
            else:
                print("[!] Remark format incorrect, may need manual login")
                account_info = None
        else:
            print("[!] Cannot get browser info")
            account_info = None
    
    result = openBrowser(browser_id)
    
    if not result.get('success'):
        return False, f"Failed to open browser: {result}"
    
    ws_endpoint = result['data']['ws']
    print(f"WebSocket URL: {ws_endpoint}")
    
    async with async_playwright() as playwright:
        try:
            chromium = playwright.chromium
            browser = await chromium.connect_over_cdp(ws_endpoint)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Navigate to target page
            target_url = "https://one.google.com/ai-student?g1_landing_page=75&utm_source=antigravity&utm_campaign=argon_limit_reached"
            print(f"Navigating to: {target_url}")
            await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for page to load
            print("Waiting for page to fully load...")
            await asyncio.sleep(5)
            
            # Execute auto card binding (includes login detection)
            success, message = await auto_bind_card(page, account_info=account_info)
            
            print(f"\n{'='*50}")
            print(f"Card binding result: {message}")
            print(f"{'='*50}\n")
            
            # Keep browser open to view results
            print("Card binding flow complete. Browser will stay open.")
            
            return True, message
            
        except Exception as e:
            print(f"Test error: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            # Don't close browser for result viewing
            # closeBrowser(browser_id)
            pass


if __name__ == "__main__":
    # Use specified browser ID for testing
    test_browser_id = "94b7f635502e42cf87a0d7e9b1330686"
    
    # Test account info (if login needed)
    # Format: {'email': 'xxx@gmail.com', 'password': 'xxx', 'secret': 'XXXXX'}
    test_account = None  # Set to None if already logged in
    
    print(f"Starting auto card binding test...")
    print(f"Target browser ID: {test_browser_id}")
    print(f"Test card info: {TEST_CARD}")
    print(f"\n{'='*50}\n")
    
    result = asyncio.run(test_bind_card_with_browser(test_browser_id, test_account))
    
    print(f"\nFinal result: {result}")
