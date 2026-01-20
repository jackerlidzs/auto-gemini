"""
One-Click Full Auto Processing GUI - Login → Status Detection → SheerID Verification → Card Binding

Automated workflow for Google One AI Student subscription process.
"""
import sys
import os
import asyncio
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QLabel, QLineEdit, QTextEdit, 
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QMessageBox, QCheckBox, QSpinBox, QGroupBox,
                              QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from playwright.async_api import async_playwright
from bit_api import openBrowser, closeBrowser
from create_window import get_browser_info, get_browser_list
from database import DBManager
from sheerid_verifier import SheerIDVerifier


class AutoAllInOneWorker(QThread):
    """One-click full auto worker thread."""
    progress_signal = pyqtSignal(str, str, str)  # browser_id, status, message
    finished_signal = pyqtSignal()
    log_signal = pyqtSignal(str)
    
    def __init__(self, accounts, cards, cards_per_account, delays, api_key, thread_count=3):
        super().__init__()
        self.accounts = accounts
        self.cards = cards
        self.cards_per_account = cards_per_account
        self.delays = delays
        self.api_key = api_key
        self.thread_count = thread_count
        self.is_running = True
    
    def run(self):
        try:
            asyncio.run(self._process_all())
        except Exception as e:
            self.log_signal.emit(f"[X] Worker thread error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.finished_signal.emit()
    
    async def _process_all(self):
        """Process all accounts (with concurrency support)."""
        card_index = 0
        card_usage_count = 0
        
        # Process accounts in batches
        for batch_start in range(0, len(self.accounts), self.thread_count):
            if not self.is_running:
                break
            
            batch_end = min(batch_start + self.thread_count, len(self.accounts))
            batch_accounts = self.accounts[batch_start:batch_end]
            
            self.log_signal.emit(f"\n{'='*50}")
            self.log_signal.emit(f"Processing accounts {batch_start+1}-{batch_end} (total {len(self.accounts)})")
            self.log_signal.emit(f"{'='*50}")
            
            # Assign cards and create tasks for each account
            tasks = []
            for i, account in enumerate(batch_accounts):
                global_index = batch_start + i
                
                # Check if need to switch to next card
                if card_usage_count >= self.cards_per_account:
                    card_index += 1
                    card_usage_count = 0
                    self.log_signal.emit(f"[Card] Switching to next card (Card #{card_index + 1})")
                
                # Check if cards are exhausted
                if card_index >= len(self.cards):
                    self.log_signal.emit("[!] Cards exhausted, stopping processing")
                    break
                
                current_card = self.cards[card_index] if card_index < len(self.cards) else None
                
                # Create async task
                task = self._process_single_account_wrapper(
                    account, 
                    current_card, 
                    global_index + 1
                )
                tasks.append(task)
                
                if current_card:
                    card_usage_count += 1
            
            # Execute this batch concurrently
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_single_account_wrapper(self, account, card_info, index):
        """Wrapper for single account processing."""
        if not self.is_running:
            return
        
        browser_id = account.get('browser_id')
        email = account.get('email')
        
        self.log_signal.emit(f"\n[{index}] Starting account: {email}")
        
        try:
            success, message = await self._process_single_account(
                browser_id, email, card_info
            )
            
            if success:
                self.progress_signal.emit(browser_id, "[OK] Complete", message)
                self.log_signal.emit(f"[{index}] [OK] {email}: {message}")
            else:
                self.progress_signal.emit(browser_id, "[X] Failed", message)
                self.log_signal.emit(f"[{index}] [X] {email}: {message}")
                
        except Exception as e:
            error_msg = f"Processing error: {e}"
            self.progress_signal.emit(browser_id, "[X] Error", error_msg)
            self.log_signal.emit(f"[{index}] [X] {email}: {error_msg}")
    
    async def _process_single_account(self, browser_id, email, card_info):
        """
        Process single account complete flow:
        1. Login
        2. Detect status
        3. Execute corresponding action based on status
        """
        try:
            # Get account info
            target_browser = get_browser_info(browser_id)
            if not target_browser:
                return False, "Cannot get browser info"
            
            remark = target_browser.get('remark', '')
            parts = remark.split('----')
            
            account_info = None
            if len(parts) >= 4:
                account_info = {
                    'email': parts[0].strip(),
                    'password': parts[1].strip(),
                    'backup': parts[2].strip(),
                    'secret': parts[3].strip()
                }
            
            # Open browser (keep open throughout)
            result = openBrowser(browser_id)
            if not result.get('success'):
                return False, f"Failed to open browser"
            
            ws_endpoint = result['data']['ws']
            
            async with async_playwright() as playwright:
                try:
                    chromium = playwright.chromium
                    browser = await chromium.connect_over_cdp(ws_endpoint)
                    context = browser.contexts[0]
                    page = context.pages[0] if context.pages else await context.new_page()
                    
                    # Import from auto_bind_card
                    from auto_bind_card import check_and_login, auto_bind_card
                    
                    # Step 1: Navigate to target page and detect login
                    self.log_signal.emit(f"  [Key] Step 1: Navigate and login detection...")
                    target_url = "https://one.google.com/ai-student?g1_landing_page=75&utm_source=antigravity&utm_campaign=argon_limit_reached"
                    
                    # Navigate to target page first
                    await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(3)
                    
                    # Then detect login
                    login_success, login_msg = await check_and_login(page, account_info)
                    if not login_success:
                        return False, f"Login failed: {login_msg}"
                    
                    self.log_signal.emit(f"  [OK] Login successful")
                    
                    # Step 2: Status detection
                    self.log_signal.emit(f"  [Search] Step 2: Status detection...")
                    await asyncio.sleep(3)
                    
                    # Detect status (using inline logic)
                    status = await self._detect_status(page)
                    self.log_signal.emit(f"  [Chart] Current status: {status}")
                    
                    # Step 3: Execute action based on status
                    if status == "link_ready":
                        # Eligible pending verification → Extract link → Verify → Bind card
                        return await self._handle_link_ready(page, email, card_info)
                        
                    elif status == "verified":
                        # Verified unbound → Bind card directly
                        return await self._handle_verified(page, card_info, account_info)
                        
                    elif status == "subscribed":
                        # Already subscribed
                        return True, "Account already subscribed, no action needed"
                        
                    elif status == "ineligible":
                        # Ineligible
                        return False, "Account ineligible"
                    
                    elif status == "error" or status == "timeout":
                        # Error or timeout during status detection
                        return False, f"Status detection failed: {status}"
                        
                    else:
                        # Other status
                        return False, f"Unknown status: {status}"
                    
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return False, str(e)
                    
        except Exception as e:
            return False, str(e)
    
    async def _detect_status(self, page):
        """
        Detect account current status.
        Returns: link_ready, verified, subscribed, ineligible, error
        """
        try:
            page_content = await page.content()
            page_text = await page.evaluate("() => document.body.innerText")
            
            # Detect keywords
            if "Subscribed" in page_content or "Already subscribed" in page_text:
                return "subscribed"
            elif "Get student offer" in page_content or "Get offer" in page_text:
                return "verified"
            elif "verify your eligibility" in page_content or "Verify eligibility" in page_text:
                return "link_ready"
            elif "not available" in page_text or "unavailable" in page_text:
                return "ineligible"
            else:
                return "error"
        except Exception:
            return "error"
    
    async def _handle_link_ready(self, page, email, card_info):
        """Handle eligible pending verification accounts."""
        try:
            self.log_signal.emit(f"  [Link] Step 3a: Extracting SheerID link...")
            
            # Extract link (inline implementation)
            try:
                # Click "verify your eligibility" button
                await page.wait_for_selector('text=verify your eligibility', timeout=10000)
                await page.click('text=verify your eligibility')
                await asyncio.sleep(3)
                
                # Wait for new page or iframe to load
                await asyncio.sleep(2)
                
                # Get current URL or link from iframe
                link = None
                current_url = page.url
                
                if "sheerid" in current_url.lower():
                    link = current_url
                else:
                    # Try to get from iframe
                    frames = page.frames
                    for frame in frames:
                        frame_url = frame.url
                        if "sheerid" in frame_url.lower():
                            link = frame_url
                            break
                
                if not link:
                    # Try to extract from page content
                    page_content = await page.content()
                    import re
                    sheerid_match = re.search(r'https://[^"\']*sheerid[^"\']*', page_content)
                    if sheerid_match:
                        link = sheerid_match.group()
            
            except Exception as e:
                self.log_signal.emit(f"  [!] Error extracting link: {e}")
                link = None
            
            if not link:
                return False, "Cannot extract SheerID link"
            
            self.log_signal.emit(f"  [OK] Link extracted: {link[:50]}...")
            
            # Save link to database
            from account_manager import AccountManager
            line = f"{link}----{email}"
            AccountManager.save_link(line)
            
            # Step 3b: Verify SheerID
            self.log_signal.emit(f"  [Check] Step 3b: SheerID verification...")
            
            verifier = SheerIDVerifier(api_key=self.api_key)
            success, vid, msg = await asyncio.to_thread(
                verifier.verify_single,
                link
            )
            
            if not success:
                return False, f"SheerID verification failed: {msg}"
            
            self.log_signal.emit(f"  [OK] SheerID verification successful")
            
            # Update status to verified
            AccountManager.move_to_verified(line)
            
            # Refresh page
            await page.reload(wait_until='domcontentloaded')
            await asyncio.sleep(5)
            
            # Step 3c: Bind card and subscribe
            return await self._handle_verified(page, card_info, None)
            
        except Exception as e:
            return False, f"Error handling link_ready status: {e}"
    
    async def _handle_verified(self, page, card_info, account_info):
        """Handle verified unbound accounts."""
        try:
            self.log_signal.emit(f"  [Card] Step 4: Bind card and subscribe...")
            
            if not card_info:
                return False, "No card available"
            
            # Use existing bind card function
            from auto_bind_card import auto_bind_card
            
            success, message = await auto_bind_card(
                page, 
                card_info=card_info, 
                account_info=account_info
            )
            
            if success:
                self.log_signal.emit(f"  [OK] Card binding and subscription successful")
                return True, "Full flow complete: Card bound and subscribed"
            else:
                return False, f"Card binding failed: {message}"
                
        except Exception as e:
            return False, f"Error during card binding: {e}"
    
    def stop(self):
        """Stop worker thread."""
        self.is_running = False


class AutoAllInOneWindow(QWidget):
    """One-click full auto processing window."""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.initUI()
        self.load_accounts()
        self.load_cards()
    
    def initUI(self):
        self.setWindowTitle("One-Click Full Auto Processing")
        self.setGeometry(100, 100, 1000, 750)
        
        layout = QVBoxLayout()
        
        # Top settings area
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout()
        
        # SheerID API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter SheerID API Key")
        settings_layout.addRow("API Key:", self.api_key_input)
        
        # Cards per account
        self.cards_per_account_spin = QSpinBox()
        self.cards_per_account_spin.setMinimum(1)
        self.cards_per_account_spin.setMaximum(100)
        self.cards_per_account_spin.setValue(1)
        settings_layout.addRow("Cards per account:", self.cards_per_account_spin)
        
        # Concurrency
        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setMinimum(1)
        self.thread_count_spin.setMaximum(20)
        self.thread_count_spin.setValue(3)
        settings_layout.addRow("Concurrency:", self.thread_count_spin)
        
        # Delay settings
        delay_layout = QHBoxLayout()
        
        self.delay_after_offer = QSpinBox()
        self.delay_after_offer.setMinimum(1)
        self.delay_after_offer.setMaximum(60)
        self.delay_after_offer.setValue(8)
        delay_layout.addWidget(QLabel("After Offer:"))
        delay_layout.addWidget(self.delay_after_offer)
        delay_layout.addWidget(QLabel("sec"))
        
        self.delay_after_add_card = QSpinBox()
        self.delay_after_add_card.setMinimum(1)
        self.delay_after_add_card.setMaximum(60)
        self.delay_after_add_card.setValue(10)
        delay_layout.addWidget(QLabel("After AddCard:"))
        delay_layout.addWidget(self.delay_after_add_card)
        delay_layout.addWidget(QLabel("sec"))
        
        self.delay_after_save = QSpinBox()
        self.delay_after_save.setMinimum(1)
        self.delay_after_save.setMaximum(60)
        self.delay_after_save.setValue(18)
        delay_layout.addWidget(QLabel("After Save:"))
        delay_layout.addWidget(self.delay_after_save)
        delay_layout.addWidget(QLabel("sec"))
        
        settings_layout.addRow("Delays:", delay_layout)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Card and account info
        info_layout = QHBoxLayout()
        self.card_count_label = QLabel("Cards: 0")
        info_layout.addWidget(self.card_count_label)
        self.account_count_label = QLabel("Accounts: 0")
        info_layout.addWidget(self.account_count_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # Account list
        accounts_label = QLabel("Pending Accounts List:")
        layout.addWidget(accounts_label)
        
        # Select all checkbox
        select_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("Select All / Deselect All")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        select_layout.addWidget(self.select_all_checkbox)
        select_layout.addStretch()
        layout.addLayout(select_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Select", "Email", "Browser ID", "Status", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # Log area
        log_label = QLabel("Run Log:")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        layout.addWidget(self.log_text)
        
        # Button area
        button_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_refresh.clicked.connect(self.refresh_all)
        button_layout.addWidget(self.btn_refresh)
        
        self.btn_start = QPushButton("Start Full Auto Processing")
        self.btn_start.clicked.connect(self.start_processing)
        button_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_processing)
        button_layout.addWidget(self.btn_stop)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_cards(self):
        """Load cards.txt file."""
        base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        cards_path = os.path.join(base_path, "cards.txt")
        
        self.cards = []
        
        if not os.path.exists(cards_path):
            self.card_count_label.setText("Cards: 0")
            return
        
        try:
            with open(cards_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('#')]
            
            for line in lines:
                if line.startswith('separator='):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    card = {
                        'number': parts[0].strip(),
                        'exp_month': parts[1].strip(),
                        'exp_year': parts[2].strip(),
                        'cvv': parts[3].strip()
                    }
                    self.cards.append(card)
            
            self.card_count_label.setText(f"Cards: {len(self.cards)}")
            self.log(f"[OK] Loaded {len(self.cards)} cards")
            
        except Exception as e:
            self.log(f"[X] Failed to load cards: {e}")
    
    def load_accounts(self):
        """Load all pending accounts."""
        try:
            DBManager.init_db()
            conn = DBManager.get_connection()
            cursor = conn.cursor()
            
            # Query all accounts not subscribed or ineligible
            cursor.execute("""
                SELECT email, password, recovery_email, secret_key, verification_link 
                FROM accounts 
                WHERE status NOT IN ('subscribed', 'ineligible')
                ORDER BY 
                    CASE status
                        WHEN 'link_ready' THEN 1
                        WHEN 'verified' THEN 2
                        ELSE 3
                    END,
                    email
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            # Get browser list
            browsers = get_browser_list(page=0, pageSize=1000)
            email_to_browser = {}
            for browser in browsers:
                remark = browser.get('remark', '')
                if '----' in remark:
                    parts = remark.split('----')
                    if parts and '@' in parts[0]:
                        browser_email = parts[0].strip()
                        browser_id = browser.get('id', '')
                        email_to_browser[browser_email] = browser_id
            
            self.table.setRowCount(0)
            self.accounts = []
            
            for row in rows:
                email = row[0]
                browser_id = email_to_browser.get(email, '')
                
                if not browser_id:
                    continue
                
                account = {
                    'email': email,
                    'password': row[1] or '',
                    'backup': row[2] or '',
                    'secret': row[3] or '',
                    'link': row[4] or '',
                    'browser_id': browser_id
                }
                self.accounts.append(account)
                
                # Add to table
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)
                
                # Checkbox
                checkbox = QCheckBox()
                checkbox.setChecked(True)
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row_idx, 0, checkbox_widget)
                
                self.table.setItem(row_idx, 1, QTableWidgetItem(account['email']))
                self.table.setItem(row_idx, 2, QTableWidgetItem(account['browser_id']))
                self.table.setItem(row_idx, 3, QTableWidgetItem("Pending"))
                self.table.setItem(row_idx, 4, QTableWidgetItem(""))
            
            self.account_count_label.setText(f"Accounts: {len(self.accounts)}")
            self.log(f"[OK] Loaded {len(self.accounts)} pending accounts")
            
        except Exception as e:
            self.log(f"[X] Failed to load accounts: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_all(self):
        """Refresh all data."""
        self.load_accounts()
        self.load_cards()
    
    def toggle_select_all(self, state):
        """Select all / Deselect all."""
        is_checked = (state == Qt.CheckState.Checked.value)
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(is_checked)
    
    def get_selected_accounts(self):
        """Get selected accounts."""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    if row < len(self.accounts):
                        selected.append(self.accounts[row])
        return selected
    
    def start_processing(self):
        """Start processing."""
        selected_accounts = self.get_selected_accounts()
        
        if not selected_accounts:
            QMessageBox.warning(self, "Notice", "Please select accounts to process first")
            return
        
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Notice", "Please enter SheerID API Key")
            return
        
        # Collect settings
        delays = {
            'after_offer': self.delay_after_offer.value(),
            'after_add_card': self.delay_after_add_card.value(),
            'after_save': self.delay_after_save.value()
        }
        
        cards_per_account = self.cards_per_account_spin.value()
        thread_count = self.thread_count_spin.value()
        
        self.log(f"\n{'='*50}")
        self.log(f"Starting full auto processing")
        self.log(f"Selected accounts: {len(selected_accounts)}")
        self.log(f"Number of cards: {len(self.cards)}")
        self.log(f"Cards per account: {cards_per_account}")
        self.log(f"Concurrency: {thread_count}")
        self.log(f"{'='*50}\n")
        
        # Create and start worker thread
        self.worker = AutoAllInOneWorker(
            selected_accounts,
            self.cards,
            cards_per_account,
            delays,
            api_key,
            thread_count
        )
        self.worker.progress_signal.connect(self.update_account_status)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_refresh.setEnabled(False)
    
    def stop_processing(self):
        """Stop processing."""
        if self.worker:
            self.worker.stop()
            self.log("[!] Stopping...")
    
    def on_finished(self):
        """Processing complete."""
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_refresh.setEnabled(True)
        self.log("\n[OK] Full auto processing task complete!")
        QMessageBox.information(self, "Complete", "Full auto processing task completed")
    
    def update_account_status(self, browser_id, status, message):
        """Update table status."""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 2) and self.table.item(row, 2).text() == browser_id:
                self.table.setItem(row, 3, QTableWidgetItem(status))
                self.table.setItem(row, 4, QTableWidgetItem(message))
                break
    
    def log(self, message):
        """Add log message."""
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    app = QApplication(sys.argv)
    window = AutoAllInOneWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
