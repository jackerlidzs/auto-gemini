"""
BitBrowser Window Batch Creation Tool - PyQt6 GUI Version

Supports template window ID input, batch window creation, auto-reads accounts.txt and proxies.txt.
Supports custom platform URL and additional URLs.
Supports listing existing windows with batch delete functionality.
UI layout: Left side for controls, right side for logs.
"""
import sys
import os
import threading
import pyotp
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QMessageBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QSplitter,
    QAbstractItemView, QSpinBox, QToolBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon
from create_window import (
    read_accounts, read_proxies, get_browser_list, get_browser_info,
    delete_browsers_by_name, delete_browser_by_id, open_browser_by_id, create_browser_window, get_next_window_name
)
from run_playwright_google import process_browser
from sheerid_verifier import SheerIDVerifier
from sheerid_gui import SheerIDWindow
import re
from web_admin.server import run_server


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


DEFAULT_TEMPLATE_CONFIG = {
    "platform": "",
    "platformIcon": "",
    "url": "",
    "name": "Default Template",
    "userName": "",
    "password": "",
    "cookie": "",
    "otherCookie": "",
    "isGlobalProxyInfo": False,
    "isIpv6": False,
    "proxyMethod": 2,
    "proxyType": "noproxy",
    "ipCheckService": "ip2location",
    "host": "",
    "port": "",
    "proxyUserName": "",
    "proxyPassword": "",
    "enableSocks5Udp": False,
    "isIpNoChange": False,
    "isDynamicIpChangeIp": True,
    "status": 0,
    "isDelete": 0,
    "isMostCommon": 0,
    "isRemove": 0,
    "abortImage": False,
    "abortMedia": False,
    "stopWhileNetError": False,
    "stopWhileCountryChange": False,
    "syncTabs": False,
    "syncCookies": False,
    "syncIndexedDb": False,
    "syncBookmarks": False,
    "syncAuthorization": True,
    "syncHistory": False,
    "syncGoogleAccount": False,
    "allowedSignin": False,
    "syncSessions": False,
    "workbench": "localserver",
    "clearCacheFilesBeforeLaunch": True,
    "clearCookiesBeforeLaunch": False,
    "clearHistoriesBeforeLaunch": False,
    "randomFingerprint": True,
    "muteAudio": False,
    "disableGpu": False,
    "enableBackgroundMode": False,
    "syncExtensions": False,
    "syncUserExtensions": False,
    "syncLocalStorage": False,
    "credentialsEnableService": False,
    "disableTranslatePopup": False,
    "stopWhileIpChange": False,
    "disableClipboard": False,
    "disableNotifications": False,
    "memorySaver": False,
    "isRandomFinger": True,
    "isSynOpen": 1,
    "coreProduct": "chrome",
    "ostype": "PC",
    "os": "Win32",
    "coreVersion": "140"
}


class WorkerThread(QThread):
    """Generic background worker thread."""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)  # result data

    def __init__(self, task_type, **kwargs):
        super().__init__()
        self.task_type = task_type
        self.kwargs = kwargs
        self.is_running = True

    def stop(self):
        self.is_running = False

    def log(self, message):
        self.log_signal.emit(message)

    def msleep(self, ms):
        """Interruptible sleep."""
        t = ms
        while t > 0 and self.is_running:
            time.sleep(0.1)
            t -= 100

    def run(self):
        if self.task_type == 'create':
            self.run_create()
        elif self.task_type == 'delete':
            self.run_delete()
        elif self.task_type == 'open':
            self.run_open()
        elif self.task_type == '2fa':
            self.run_2fa()
        elif self.task_type == 'sheerlink':
            self.run_sheerlink()
        elif self.task_type == 'verify_sheerid':
            self.run_verify_sheerid()

    def run_sheerlink(self):
        """Execute SheerLink extraction task (multi-threaded) + statistics."""
        ids_to_process = self.kwargs.get('ids', [])
        thread_count = self.kwargs.get('thread_count', 1)
        
        if not ids_to_process:
            self.finished_signal.emit({'type': 'sheerlink', 'count': 0})
            return
        
        self.log(f"\n[Start] SheerID Link extraction task, {len(ids_to_process)} windows, concurrency: {thread_count}...")
        
        # Stats counters
        stats = {
            'link_unverified': 0,
            'link_verified': 0,
            'subscribed': 0,
            'ineligible': 0,
            'timeout': 0,
            'error': 0
        }
        
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            future_to_id = {}
            for bid in ids_to_process:
                # Callback to log progress with ID prefix
                # Using default arg b=bid to capture loop variable value
                callback = lambda msg, b=bid: self.log_signal.emit(f"[{b}] {msg}")
                future = executor.submit(process_browser, bid, log_callback=callback)
                future_to_id[future] = bid
            
            finished_tasks = 0
            for future in as_completed(future_to_id):
                if not self.is_running:
                    self.log('[User Action] Task stopped (waiting for current threads to complete)')
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                bid = future_to_id[future]
                finished_tasks += 1
                try:
                    success, msg = future.result()
                    if success:
                        self.log(f"[Success] ({finished_tasks}/{len(ids_to_process)}) {bid}: {msg}")
                        success_count += 1
                    else:
                        self.log(f"[Failed] ({finished_tasks}/{len(ids_to_process)}) {bid}: {msg}")
                        
                    # Stats Logic
                    if "Verified Link" in msg or "Get Offer" in msg or "Offer Ready" in msg or "Verified" in msg:
                        stats['link_verified'] += 1
                    elif "Unverified Link" in msg or "Link Found" in msg or "Link Extracted" in msg:
                        stats['link_unverified'] += 1
                    elif "Subscribed" in msg:
                        stats['subscribed'] += 1
                    elif "Ineligible" in msg or "not available" in msg:
                        stats['ineligible'] += 1
                    elif "Timeout" in msg:
                        stats['timeout'] += 1
                    else:
                        stats['error'] += 1
                        
                except Exception as e:
                    self.log(f"[Exception] ({finished_tasks}/{len(ids_to_process)}) {bid}: {e}")
                    stats['error'] += 1

        # Final Report
        summary_msg = (
            f"Task Statistics Report:\n"
            f"--------------------------------\n"
            f"Eligible Pending:     {stats['link_unverified']}\n"
            f"Verified Unbound:     {stats['link_verified']}\n"
            f"Subscribed:           {stats['subscribed']}\n"
            f"Ineligible:           {stats['ineligible']}\n"
            f"Timeout/Error:        {stats['timeout'] + stats['error']}\n"
            f"--------------------------------\n"
            f"Total processed: {finished_tasks}/{len(ids_to_process)}"
        )
        self.log(f"\n{summary_msg}")
        self.finished_signal.emit({'type': 'sheerlink', 'count': success_count, 'summary': summary_msg})

    def run_verify_sheerid(self):
        links = self.kwargs.get('links', [])
        thread_count = self.kwargs.get('thread_count', 1)
        
        self.log(f"\n[Start] Batch verification of {len(links)} links (concurrency: {thread_count})...")
        
        tasks = []
        vid_map = {}  # ID -> Original Line
        
        for line in links:
            line = line.strip()
            if not line:
                continue
            
            vid = None
            # Priority: extract verificationId from params
            match_param = re.search(r'verificationId=([a-zA-Z0-9]+)', line)
            if match_param:
                vid = match_param.group(1)
            else:
                # Fallback: extract ID from path
                match_path = re.search(r'verify/([a-zA-Z0-9]+)', line)
                if match_path:
                    vid = match_path.group(1)
            
            if vid:
                tasks.append(vid)
                vid_map[vid] = line
        
        if not tasks:
            self.log("[Error] No valid verificationId found")
            self.finished_signal.emit({'type': 'verify_sheerid', 'count': 0})
            return

        batches = [tasks[i:i + 5] for i in range(0, len(tasks), 5)]
        
        success_count = 0
        fail_count = 0
        
        base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        path_success = os.path.join(base_path, "sheerID_verified_success.txt")
        path_fail = os.path.join(base_path, "sheerID_verified_failed.txt")

        # Define Callback
        def status_callback(vid, msg):
            self.log(f"[Checking] {vid[:6]}...: {msg}")

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = []
            for batch in batches:
                futures.append(executor.submit(self._verify_batch_wrapper, batch, status_callback))
            
            for future in as_completed(futures):
                if not self.is_running:
                    self.log('[User Action] Task stopped')
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    results = future.result()
                    for vid, res in results.items():
                        status = res.get("currentStep") or res.get("status")
                        msg = res.get("message", "")
                        
                        original_line = vid_map.get(vid, vid)
                        
                        if status == "success":
                            success_count += 1
                            self.log(f"[Verify Success] {vid}")
                            with open(path_success, 'a', encoding='utf-8') as f:
                                f.write(f"{original_line} | Success\n")
                        else:
                            fail_count += 1
                            self.log(f"[Verify Failed] {vid}: {msg}")
                            with open(path_fail, 'a', encoding='utf-8') as f:
                                f.write(f"{original_line} | {msg}\n")
                except Exception as e:
                    self.log(f"[Exception] Batch error: {e}")

        self.log(f"[Complete] Verification finished. Success: {success_count}, Failed: {fail_count}")
        self.finished_signal.emit({'type': 'verify_sheerid', 'count': success_count})

    def _verify_batch_wrapper(self, batch_ids, callback=None):
        v = SheerIDVerifier()
        return v.verify_batch(batch_ids, callback=callback)

    def run_open(self):
        """Execute batch open task."""
        ids_to_open = self.kwargs.get('ids', [])
        if not ids_to_open:
            self.finished_signal.emit({'type': 'open', 'success_count': 0})
            return

        self.log(f"\n[Start] Preparing to open {len(ids_to_open)} windows...")
        success_count = 0
        
        for i, browser_id in enumerate(ids_to_open, 1):
            if not self.is_running:
                self.log('[User Action] Open task stopped')
                break
            
            self.log(f"Opening ({i}/{len(ids_to_open)}): {browser_id}")
            if open_browser_by_id(browser_id):
                self.log(f"[Success] Launching window {browser_id}")
                success_count += 1
            else:
                self.log(f"[Failed] Window {browser_id} request failed")
            
            # Required delay to prevent API overload
            self.msleep(1000)
        
        self.log(f"[Complete] Open task finished, successfully requested {success_count}/{len(ids_to_open)}")
        self.finished_signal.emit({'type': 'open', 'success_count': success_count})

    def run_2fa(self):
        """Generate and save 2FA codes."""
        try:
            self.log("Fetching window list via API for code generation...")
            
            # 1. Get current window list (try to get more to cover all)
            browsers = get_browser_list(page=0, pageSize=100)
            if not browsers:
                self.log("No window list retrieved")
                self.finished_signal.emit({'type': '2fa', 'codes': {}})
                return

            codes_map = {}
            file_lines = []
            
            count = 0
            for browser in browsers:
                if not self.is_running:
                    break
                
                # Priority: get secret from remark (4th segment)
                secret = None
                remark = browser.get('remark', '')
                if remark:
                    parts = remark.split('----')
                    if len(parts) >= 4:
                        secret = parts[3].strip()
                
                # If not in remark, try from field
                if not secret:
                    secret = browser.get('faSecretKey')

                if secret and secret.strip():
                    try:
                        # Clean secret
                        s = secret.strip().replace(" ", "")
                        totp = pyotp.TOTP(s)
                        code = totp.now()
                        
                        bid = browser.get('id')
                        codes_map[bid] = code
                        file_lines.append(f"{code}----{s}")
                        count += 1
                    except Exception as e:
                        pass
            
            # Save to file
            if file_lines:
                # Use absolute path relative to executable
                base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
                save_path = os.path.join(base_path, '2fa_codes.txt')
                
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(file_lines))
                self.log(f"Saved {len(file_lines)} codes to {save_path}")
            
            self.log(f"2FA refresh complete, generated {count} codes")
            self.finished_signal.emit({'type': '2fa', 'codes': codes_map})
            
        except Exception as e:
            self.log(f"2FA processing exception: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.finished_signal.emit({'type': '2fa', 'codes': {}})

    def run_delete(self):
        """Execute batch delete task."""
        ids_to_delete = self.kwargs.get('ids', [])
        if not ids_to_delete:
            self.finished_signal.emit({'success_count': 0, 'total': 0})
            return

        self.log(f"\n[Start] Preparing to delete {len(ids_to_delete)} windows...")
        success_count = 0
        
        for i, browser_id in enumerate(ids_to_delete, 1):
            if not self.is_running:
                self.log('[User Action] Delete task stopped')
                break
            
            self.log(f"Deleting ({i}/{len(ids_to_delete)}): {browser_id}")
            if delete_browser_by_id(browser_id):
                self.log(f"[Success] Deleted window {browser_id}")
                success_count += 1
            else:
                self.log(f"[Failed] Failed to delete window {browser_id}")
        
        self.log(f"[Complete] Delete task finished, successfully deleted {success_count}/{len(ids_to_delete)}")
        self.finished_signal.emit({'type': 'delete', 'success_count': success_count})

    def run_create(self):
        """Execute create task."""
        template_id = self.kwargs.get('template_id')
        template_config = self.kwargs.get('template_config')
        
        platform_url = self.kwargs.get('platform_url')
        extra_url = self.kwargs.get('extra_url')
        name_prefix = self.kwargs.get('name_prefix')

        try:
            # Read account info
            accounts_file = 'accounts.txt'
            accounts = read_accounts(accounts_file)
            
            if not accounts:
                self.log("[Error] No valid account info found")
                self.log("Please ensure accounts.txt exists and has correct format")
                self.log("Format: Email----Password----Backup Email----2FA Secret")
                self.finished_signal.emit({'type': 'create', 'success_count': 0})
                return
            
            self.log(f"[Info] Found {len(accounts)} accounts")
            
            # Read proxy info
            proxies_file = 'proxies.txt'
            proxies = read_proxies(proxies_file)
            self.log(f"[Info] Found {len(proxies)} proxies")
            
            # Get reference window config
            if template_config:
                reference_config = template_config
                ref_name = reference_config.get('name', 'Default Template')
                self.log(f"[Info] Using built-in default template")
            else:
                reference_config = get_browser_info(template_id)
                if not reference_config:
                    self.log(f"[Error] Cannot get template window config")
                    self.finished_signal.emit({'type': 'create', 'success_count': 0})
                    return
                ref_name = reference_config.get('name', 'Unknown')
                self.log(f"[Info] Using template window: {ref_name} (ID: {template_id})")
            
            # Show platform and URL info
            if platform_url:
                self.log(f"[Info] Platform URL: {platform_url}")
            if extra_url:
                self.log(f"[Info] Extra URL: {extra_url}")
            
            # Delete windows named "LocalProxy_2" if reference is "LocalProxy_1"
            if ref_name.startswith('LocalProxy_'):
                try:
                    next_name = get_next_window_name(ref_name)
                    if next_name == "LocalProxy_2":
                        self.log(f"\n[Step] Cleaning up old 'LocalProxy_2' windows...")
                        deleted_count = delete_browsers_by_name("LocalProxy_2")
                        if deleted_count > 0:
                            self.log(f"[Cleanup] Deleted {deleted_count} old windows")
                except:
                    pass
            
            # Create window for each account
            success_count = 0
            for i, account in enumerate(accounts, 1):
                if not self.is_running:
                    self.log("\n[User Action] Create task stopped")
                    break
                
                self.log(f"\n{'='*40}")
                self.log(f"[Progress] ({i}/{len(accounts)}) Creating: {account['email']}")
                
                # Get corresponding proxy (if available)
                proxy = proxies[i - 1] if i - 1 < len(proxies) else None
                
                browser_id, error_msg = create_browser_window(
                    account, 
                    template_id if not template_config else None,
                    proxy,
                    platform=platform_url if platform_url else None,
                    extra_url=extra_url if extra_url else None,
                    template_config=template_config,
                    name_prefix=name_prefix
                )
                
                if browser_id:
                    success_count += 1
                    self.log(f"[Success] Window created! ID: {browser_id}")
                else:
                    self.log(f"[Failed] Window creation failed: {error_msg}")
            
            self.log(f"\n{'='*40}")
            self.log(f"[Complete] Total created {success_count}/{len(accounts)} windows")
            
            self.finished_signal.emit({'type': 'create', 'success_count': success_count})
            
        except Exception as e:
            self.log(f"[Error] Exception during creation: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.finished_signal.emit({'type': 'create', 'success_count': 0})


class BrowserWindowCreatorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window icon
        try:
            icon_path = resource_path("beta-1.svg")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.ensure_data_files()
        self.worker_thread = None
        self.init_ui()

    def ensure_data_files(self):
        """Ensure necessary data files exist."""
        base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        files = ["sheerIDlink.txt", "ineligible.txt", "2fa_codes.txt", "subscribed.txt", "verified_no_card.txt", "error.txt"]
        for f in files:
            path = os.path.join(base_path, f)
            if not os.path.exists(path):
                try:
                    with open(path, 'w', encoding='utf-8') as file:
                        pass
                except Exception as e:
                    print(f"Failed to create {f}: {e}")
        
    def init_function_panel(self):
        """Initialize left function panel."""
        self.function_panel = QWidget()
        self.function_panel.setFixedWidth(250)
        self.function_panel.setVisible(False)  # Hidden by default
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.function_panel.setLayout(layout)
        
        # 1. Title
        title = QLabel("Toolbox")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(title)
        
        # 2. Sectioned toolbox
        self.toolbox = QToolBox()
        self.toolbox.setStyleSheet("""
            QToolBox::tab {
                background: #e1e1e1;
                border-radius: 5px;
                color: #555;
                font-weight: bold;
            }
            QToolBox::tab:selected {
                background: #d0d0d0;
                color: black;
            }
        """)
        layout.addWidget(self.toolbox)
        
        # --- Google Section ---
        google_page = QWidget()
        google_layout = QVBoxLayout()
        google_layout.setContentsMargins(5, 10, 5, 10)
        
        # Move btn_sheerlink here
        self.btn_sheerlink = QPushButton("One-Click Get G-SheerLink")
        self.btn_sheerlink.setFixedHeight(40)
        self.btn_sheerlink.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sheerlink.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #4CAF50;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.btn_sheerlink.clicked.connect(self.action_get_sheerlink)
        google_layout.addWidget(self.btn_sheerlink)
        
        # New Button: Verify SheerID
        self.btn_verify_sheerid = QPushButton("Batch Verify SheerID Links")
        self.btn_verify_sheerid.setFixedHeight(40)
        self.btn_verify_sheerid.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_verify_sheerid.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #2196F3;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.btn_verify_sheerid.clicked.connect(self.action_verify_sheerid)
        google_layout.addWidget(self.btn_verify_sheerid)
        
        # One-click bind card button
        self.btn_bind_card = QPushButton("One-Click Bind Card")
        self.btn_bind_card.setFixedHeight(40)
        self.btn_bind_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bind_card.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #FF9800;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.btn_bind_card.clicked.connect(self.action_bind_card)
        google_layout.addWidget(self.btn_bind_card)
        
        # One-click full auto button
        self.btn_auto_all = QPushButton("One-Click Full Auto")
        self.btn_auto_all.setFixedHeight(40)
        self.btn_auto_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto_all.setStyleSheet("""
            QPushButton {
                text-align: left; 
                padding-left: 15px; 
                font-weight: bold; 
                color: white;
                background-color: #9C27B0;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        self.btn_auto_all.clicked.connect(self.action_auto_all)
        google_layout.addWidget(self.btn_auto_all)
        
        google_layout.addStretch()
        google_page.setLayout(google_layout)
        self.toolbox.addItem(google_page, "Google Section")
        
        # --- Microsoft Section ---
        ms_page = QWidget()
        self.toolbox.addItem(ms_page, "Microsoft Section")
        
        # --- Facebook Section ---
        fb_page = QWidget()
        self.toolbox.addItem(fb_page, "Facebook Section")
        
        # --- Telegram Section ---
        tg_page = QWidget()
        tg_layout = QVBoxLayout()
        tg_layout.addWidget(QLabel("Feature in development..."))
        tg_layout.addStretch()
        tg_page.setLayout(tg_layout)
        self.toolbox.addItem(tg_page, "Telegram Section")
        
        # Default: expand Google
        self.toolbox.setCurrentIndex(0)

    def init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("BitBrowser Window Manager")
        self.setWindowIcon(QIcon(resource_path("beta-1.svg")))
        self.resize(1300, 800)
        
        # Init Side Panel
        self.init_function_panel()
        
        # Main window widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Main layout - horizontal
        main_layout = QHBoxLayout()
        main_layout.setSpacing(5)
        main_widget.setLayout(main_layout)
        
        # 1. Add Function Panel (Leftmost)
        main_layout.addWidget(self.function_panel)
        
        # ================== Left Area (Controls + List) ==================
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        # --- Top Bar: Toggle Logic + Title + Global Settings ---
        top_bar_layout = QHBoxLayout()
        
        # Toggle Button
        self.btn_toggle_tools = QPushButton("Toolbox")
        self.btn_toggle_tools.setCheckable(True)
        self.btn_toggle_tools.setChecked(False)
        self.btn_toggle_tools.setFixedHeight(30)
        self.btn_toggle_tools.setStyleSheet("""
            QPushButton { background-color: #607D8B; color: white; border-radius: 4px; padding: 5px 10px; }
            QPushButton:checked { background-color: #455A64; }
        """)
        self.btn_toggle_tools.clicked.connect(lambda checked: self.function_panel.setVisible(checked))
        top_bar_layout.addWidget(self.btn_toggle_tools)
        
        # Title
        title_label = QLabel("Control Panel")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setContentsMargins(10, 0, 10, 0)
        top_bar_layout.addWidget(title_label)
        
        top_bar_layout.addStretch()
        
        # Global Thread Spinbox
        top_bar_layout.addWidget(QLabel("Global Concurrency:"))
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 50)
        self.thread_spinbox.setValue(1)
        self.thread_spinbox.setFixedSize(70, 30)
        self.thread_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thread_spinbox.setStyleSheet("font-size: 14px; font-weight: bold; color: #E91E63;")
        self.thread_spinbox.setToolTip("Concurrency for all multi-threaded tasks (1-50)")
        top_bar_layout.addWidget(self.thread_spinbox)
        
        left_layout.addLayout(top_bar_layout)
        
        # 2. Configuration Area
        config_group = QGroupBox("Creation Parameters")
        config_layout = QVBoxLayout()
        
        # Template ID
        input_layout1 = QHBoxLayout()
        input_layout1.addWidget(QLabel("Template Window ID:"))
        self.template_id_input = QLineEdit()
        self.template_id_input.setPlaceholderText("Enter template window ID")
        input_layout1.addWidget(self.template_id_input)
        config_layout.addLayout(input_layout1)

        # Window name prefix
        input_layout_prefix = QHBoxLayout()
        input_layout_prefix.addWidget(QLabel("Window Prefix:"))
        self.name_prefix_input = QLineEdit()
        self.name_prefix_input.setPlaceholderText("Optional, defaults to template name or 'Default Template'")
        input_layout_prefix.addWidget(self.name_prefix_input)
        config_layout.addLayout(input_layout_prefix)
        
        # URL configuration
        input_layout2 = QHBoxLayout()
        input_layout2.addWidget(QLabel("Platform URL:"))
        self.platform_url_input = QLineEdit()
        self.platform_url_input.setPlaceholderText("Optional, platform URL")
        input_layout2.addWidget(self.platform_url_input)
        config_layout.addLayout(input_layout2)
        
        input_layout3 = QHBoxLayout()
        input_layout3.addWidget(QLabel("Extra URL:"))
        self.extra_url_input = QLineEdit()
        self.extra_url_input.setPlaceholderText("Optional, comma-separated")
        input_layout3.addWidget(self.extra_url_input)
        config_layout.addLayout(input_layout3)
        
        # File path hints
        file_info_layout = QHBoxLayout()
        self.accounts_label = QLabel("[OK] accounts.txt")
        self.accounts_label.setStyleSheet("color: green;")
        self.proxies_label = QLabel("[OK] proxies.txt")
        self.proxies_label.setStyleSheet("color: green;")
        file_info_layout.addWidget(self.accounts_label)
        file_info_layout.addWidget(self.proxies_label)
        file_info_layout.addStretch()
        config_layout.addLayout(file_info_layout)
        
        config_group.setLayout(config_layout)
        left_layout.addWidget(config_group)
        
        # 3. Creation control buttons
        create_btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Create Windows from Template")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self.start_creation)
        
        self.stop_btn = QPushButton("Stop Task")
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setEnabled(False)
        
        create_btn_layout.addWidget(self.start_btn)
        
        self.start_default_btn = QPushButton("Create with Default Template")
        self.start_default_btn.setFixedHeight(40)
        self.start_default_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.start_default_btn.clicked.connect(self.start_creation_default)
        create_btn_layout.addWidget(self.start_default_btn)
        
        create_btn_layout.addWidget(self.stop_btn)
        left_layout.addLayout(create_btn_layout)
        
        # 4. Window list section
        list_group = QGroupBox("Existing Windows List")
        list_layout = QVBoxLayout()
        
        # List action buttons
        list_action_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.refresh_browser_list)
        
        self.btn_2fa = QPushButton("Refresh & Save 2FA Codes")
        self.btn_2fa.setStyleSheet("color: purple; font-weight: bold;")
        self.btn_2fa.clicked.connect(self.action_refresh_2fa)

        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        
        self.open_btn = QPushButton("Open Selected")
        self.open_btn.setStyleSheet("color: blue; font-weight: bold;")
        self.open_btn.clicked.connect(self.open_selected_browsers)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setStyleSheet("color: red;")
        self.delete_btn.clicked.connect(self.delete_selected_browsers)
        
        list_action_layout.addWidget(self.refresh_btn)
        list_action_layout.addWidget(self.btn_2fa)
        list_action_layout.addWidget(self.select_all_checkbox)
        list_action_layout.addStretch()
        list_action_layout.addWidget(self.open_btn)
        list_action_layout.addWidget(self.delete_btn)
        list_layout.addLayout(list_action_layout)
        
        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Select", "Name", "Window ID", "2FA Code", "Remark"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Checkbox
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)      # Name
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)      # ID
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)      # 2FA
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)          # Remark
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        list_layout.addWidget(self.table)
        
        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group)
        
        # Add left side to main layout
        main_layout.addWidget(left_widget, 3)
        
        # ================== Right Area (Log) ==================
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        log_label = QLabel("Run Status Log")
        log_label.setFont(title_font)
        right_layout.addWidget(log_label)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setStyleSheet("background-color: #f5f5f5;")
        right_layout.addWidget(self.status_text)
        
        # Add clear log button
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.status_text.clear)
        right_layout.addWidget(clear_log_btn)
        
        # Add right side to main layout
        main_layout.addWidget(right_widget, 2)
        
        # Initial load
        QTimer.singleShot(100, self.refresh_browser_list)
        self.check_files()

    def check_files(self):
        """Check if files exist and update UI."""
        accounts_exists = os.path.exists('accounts.txt')
        proxies_exists = os.path.exists('proxies.txt')
        
        if not accounts_exists:
            self.accounts_label.setText("[X] accounts.txt missing")
            self.accounts_label.setStyleSheet("color: red;")
        if not proxies_exists:
            self.proxies_label.setText("[!] proxies.txt not found")
            self.proxies_label.setStyleSheet("color: orange;")

    def log(self, message):
        """Add log entry."""
        self.status_text.append(message)
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_text.setTextCursor(cursor)

    def refresh_browser_list(self):
        """Refresh window list to table."""
        self.table.setRowCount(0)
        self.select_all_checkbox.setChecked(False)
        self.log("Refreshing window list...")
        QApplication.processEvents()
        
        try:
            browsers = get_browser_list()
            if not browsers:
                self.log("No window list retrieved")
                return
            
            self.table.setRowCount(len(browsers))
            for i, browser in enumerate(browsers):
                # Checkbox
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(i, 0, chk_item)
                
                # Name
                name = str(browser.get('name', ''))
                self.table.setItem(i, 1, QTableWidgetItem(name))
                
                # ID
                bid = str(browser.get('id', ''))
                self.table.setItem(i, 2, QTableWidgetItem(bid))
                
                # 2FA (Initial empty)
                self.table.setItem(i, 3, QTableWidgetItem(""))
                
                # Remark
                remark = str(browser.get('remark', ''))
                self.table.setItem(i, 4, QTableWidgetItem(remark))
            
            self.log(f"List refresh complete, {len(browsers)} windows total")
            
        except Exception as e:
            self.log(f"[Error] Refresh list failed: {e}")

    def action_refresh_2fa(self):
        """Refresh and save 2FA codes."""
        self.log("Fetching all window info to generate codes...")
        self.start_worker_thread('2fa')

    def action_get_sheerlink(self):
        """One-click get G-sheerlink."""
        ids = self.get_selected_browser_ids()
        if not ids:
            QMessageBox.warning(self, "Notice", "Please select windows to process in the list first")
            return
        
        thread_count = self.thread_spinbox.value()
        msg = f"Are you sure you want to extract SheerID links from the selected {len(ids)} windows?\n"
        msg += f"Current concurrency mode: {thread_count} threads\n"
        if thread_count > 1:
            msg += "[!] Note: Multiple browser windows will open simultaneously, ensure sufficient system resources."
        
        reply = QMessageBox.question(self, 'Confirm Operation', msg,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_worker_thread('sheerlink', ids=ids, thread_count=thread_count)

    def action_verify_sheerid(self):
        """Open SheerID batch verification window."""
        try:
            if not hasattr(self, 'verify_window') or self.verify_window is None:
                self.verify_window = SheerIDWindow(self)
            
            self.verify_window.show()
            self.verify_window.raise_()
            self.verify_window.activateWindow()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot open verification window: {e}")
    
    def action_bind_card(self):
        """Open one-click bind card window."""
        try:
            from bind_card_gui import BindCardWindow
            
            if not hasattr(self, 'bind_card_window') or self.bind_card_window is None:
                self.bind_card_window = BindCardWindow()
            
            self.bind_card_window.show()
            self.bind_card_window.raise_()
            self.bind_card_window.activateWindow()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot open card binding window: {e}")
            import traceback
            traceback.print_exc()
    
    def action_auto_all(self):
        """Open one-click full auto window."""
        try:
            from auto_all_in_one_gui import AutoAllInOneWindow
            
            if not hasattr(self, 'auto_all_window') or self.auto_all_window is None:
                self.auto_all_window = AutoAllInOneWindow()
            
            self.auto_all_window.show()
            self.auto_all_window.raise_()
            self.auto_all_window.activateWindow()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot open full auto window: {e}")
            import traceback
            traceback.print_exc()
        
    def open_selected_browsers(self):
        """Open selected windows."""
        ids = self.get_selected_browser_ids()
        if not ids:
            QMessageBox.warning(self, "Notice", "Please select windows to open first")
            return
        
        self.start_worker_thread('open', ids=ids)

    def toggle_select_all(self, state):
        """Select all / Deselect all."""
        is_checked = (state == Qt.CheckState.Checked.value)  # value of Qt.CheckState.Checked is 2
        # Note: In Qt6, state is int
        # stateChanged emits int
        # Qt.CheckState.Checked.value is 2
        
        row_count = self.table.rowCount()
        for i in range(row_count):
            item = self.table.item(i, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked if state == 2 else Qt.CheckState.Unchecked)

    def get_selected_browser_ids(self):
        """Get selected window ID list."""
        ids = []
        row_count = self.table.rowCount()
        for i in range(row_count):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                # ID is in column 2
                id_item = self.table.item(i, 2)
                if id_item:
                    ids.append(id_item.text())
        return ids

    def delete_selected_browsers(self):
        """Delete selected windows."""
        ids = self.get_selected_browser_ids()
        if not ids:
            QMessageBox.warning(self, "Notice", "Please select windows to delete first")
            return
        
        reply = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to delete the selected {len(ids)} windows?\nThis action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_worker_thread('delete', ids=ids)

    def start_creation(self):
        """Start create task."""
        template_id = self.template_id_input.text().strip()
        if not template_id:
            QMessageBox.warning(self, "Warning", "Please enter template window ID")
            return
            
        platform_url = self.platform_url_input.text().strip()
        extra_url = self.extra_url_input.text().strip()
        name_prefix = self.name_prefix_input.text().strip()
        
        self.update_ui_state(True)
        self.log(f"Starting create task... Template ID: {template_id}")
        
        self.worker_thread = WorkerThread(
            'create', 
            template_id=template_id,
            platform_url=platform_url, 
            extra_url=extra_url,
            name_prefix=name_prefix
        )
        self.worker_thread.log_signal.connect(self.log)
        self.worker_thread.finished_signal.connect(self.on_worker_finished)
        self.worker_thread.start()

    def start_worker_thread(self, task_type, **kwargs):
        """Start background thread."""
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Notice", "A task is currently running, please wait...")
            return
            
        self.worker_thread = WorkerThread(task_type, **kwargs)
        self.worker_thread.log_signal.connect(self.log)
        self.worker_thread.finished_signal.connect(self.on_worker_finished)
        self.worker_thread.start()
        
        self.update_ui_state(running=True)

    def update_ui_state(self, running):
        """Update UI button states."""
        self.start_btn.setEnabled(not running)
        self.start_default_btn.setEnabled(not running)
        self.delete_btn.setEnabled(not running)
        self.open_btn.setEnabled(not running)
        self.btn_2fa.setEnabled(not running)
        self.btn_sheerlink.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.refresh_btn.setEnabled(not running)
        self.template_id_input.setEnabled(not running)
        self.name_prefix_input.setEnabled(not running)

    def start_creation_default(self):
        """Start create task using default template."""
        platform_url = self.platform_url_input.text().strip()
        extra_url = self.extra_url_input.text().strip()
        name_prefix = self.name_prefix_input.text().strip()
        
        self.update_ui_state(True)
        self.log(f"Starting create task... Using default config template")
        
        self.start_worker_thread(
            'create', 
            template_config=DEFAULT_TEMPLATE_CONFIG,
            platform_url=platform_url, 
            extra_url=extra_url,
            name_prefix=name_prefix
        )

    def stop_task(self):
        """Stop current task."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.log("[User Action] Stopping task...")
            self.stop_btn.setEnabled(False)  # Prevent repeated clicks

    def on_worker_finished(self, result):
        """Task finished callback."""
        self.update_ui_state(running=False)
        self.log(f"Task finished")
        
        # If delete operation, refresh list after completion
        if result.get('type') == 'delete':
            self.refresh_browser_list()
        # If create operation, also refresh list to see new windows
        elif result.get('type') == 'create':
            self.refresh_browser_list()
        # 2FA refresh result
        elif result.get('type') == '2fa':
            codes = result.get('codes', {})
            row_count = self.table.rowCount()
            for i in range(row_count):
                id_item = self.table.item(i, 2)  # ID Column
                if id_item:
                    bid = id_item.text()
                    if bid in codes:
                        self.table.setItem(i, 3, QTableWidgetItem(str(codes[bid])))
            QMessageBox.information(self, "Complete", "2FA codes updated and saved")
        # Open operation
        elif result.get('type') == 'open':
            pass
            
        elif result.get('type') == 'sheerlink':
            count = result.get('count', 0)
            summary = result.get('summary')
            if summary:
                QMessageBox.information(self, "Task Complete", summary)
            else:
                QMessageBox.information(self, "Complete", f"SheerLink extraction task finished\nSuccessfully extracted: {count}\nResults saved in sheerIDlink.txt")

        elif result.get('type') == 'verify_sheerid':
            count = result.get('count', 0)
            QMessageBox.information(self, "Complete", f"SheerID batch verification finished\nSuccess: {count}\nResults saved to sheerID_verified_success/failed.txt")

    def update_ui_state(self, running):
        """Update UI button states."""
        self.start_btn.setEnabled(not running)
        self.delete_btn.setEnabled(not running)
        self.open_btn.setEnabled(not running)
        self.btn_2fa.setEnabled(not running)
        self.btn_sheerlink.setEnabled(not running)
        self.btn_verify_sheerid.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.refresh_btn.setEnabled(not running)


def main():
    try:
        t = threading.Thread(target=run_server, args=(8080,), daemon=True)
        t.start()
        print("Web Admin started on http://localhost:8080")
    except Exception as e:
        print(f"Error starting Web Admin: {e}")

    # Ensure SVG support when packaging
    import PyQt6.QtSvg

    # Fix taskbar icon on Windows
    import ctypes
    try:
        myappid = 'leclee.bitbrowser.automanager.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except:
        pass

    app = QApplication(sys.argv)
    
    # Set global font
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    # Set global icon
    icon_path = resource_path("beta-1.svg")
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        app.setWindowIcon(icon)
    else:
        # If icon not found in packaged environment, show warning
        if hasattr(sys, '_MEIPASS'):
            QMessageBox.warning(None, "Icon Missing", f"Icon not found at: {icon_path}")
    
    window = BrowserWindowCreatorGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
