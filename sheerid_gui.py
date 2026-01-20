"""
SheerID Batch Verification GUI

PyQt6 GUI for batch verification of SheerID links.
Reads links from sheerIDlink.txt and allows batch verification via API.
"""
import sys
import os
import re
import time
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, 
    QMessageBox, QWidget, QAbstractItemView, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from sheerid_verifier import SheerIDVerifier
from account_manager import AccountManager


class VerifyWorker(QThread):
    """Worker thread for batch verification."""
    progress_signal = pyqtSignal(dict)  # {vid: ..., status: ..., msg: ...}
    finished_signal = pyqtSignal()

    def __init__(self, api_key, links, thread_count=1):
        super().__init__()
        self.api_key = api_key
        self.links = links  # List of dicts: [{'vid': '...', 'line': '...'}, ...]
        self.thread_count = thread_count
        self.is_running = True

    def run(self):
        verifier = SheerIDVerifier(api_key=self.api_key)
        
        # Strategy: Process in batches of 5
        tasks = [item['vid'] for item in self.links]
        batches = [tasks[i:i + 5] for i in range(0, len(tasks), 5)]
        
        def callback(vid, msg):
            if not self.is_running:
                return
            self.progress_signal.emit({'vid': vid, 'status': 'Running', 'msg': msg})

        for batch in batches:
            if not self.is_running:
                break
            
            # Update status to Processing
            for vid in batch:
                self.progress_signal.emit({'vid': vid, 'status': 'Processing', 'msg': 'Submitting...'})

            results = verifier.verify_batch(batch, callback=callback)
            
            for vid, res in results.items():
                status = res.get("currentStep") or res.get("status")
                msg = res.get("message", "")
                
                if status == "success":
                    # Move to verified
                    for item in self.links:
                        if item['vid'] == vid:
                            try:
                                AccountManager.move_to_verified(item['line'])
                            except Exception as e:
                                msg += f" (Move failed: {e})"
                            break

                self.progress_signal.emit({'vid': vid, 'status': status, 'msg': msg})
                
        self.finished_signal.emit()

    def stop(self):
        self.is_running = False


class SheerIDWindow(QDialog):
    """Main SheerID batch verification window."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SheerID Batch Verification Tool")
        self.resize(1100, 600)
        
        self.verifier = SheerIDVerifier()  # For cancellation
        self.worker = None
        self.vid_row_map = {}  # vid -> row_index
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 1. Top Control Bar
        top_layout = QHBoxLayout()
        
        top_layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit("")
        self.api_key_input.setFixedWidth(250)
        top_layout.addWidget(self.api_key_input)
        
        self.btn_load = QPushButton("Refresh File")
        self.btn_load.clicked.connect(self.load_data)
        top_layout.addWidget(self.btn_load)
        
        self.cb_select_all = QCheckBox("Select All")
        self.cb_select_all.stateChanged.connect(self.toggle_select_all)
        top_layout.addWidget(self.cb_select_all)
        
        self.btn_start = QPushButton("Verify Selected")
        self.btn_start.clicked.connect(self.start_verify)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        top_layout.addWidget(self.btn_start)
        
        self.btn_cancel = QPushButton("Cancel Selected")
        self.btn_cancel.clicked.connect(self.cancel_selected)
        self.btn_cancel.setStyleSheet("background-color: #f44336; color: white;")
        top_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(top_layout)
        
        # 2. Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Select", "Verification ID", "Original Data (Account/Link)", "Status", "Details/Progress"])
        self.table.setColumnWidth(0, 50)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        self.setLayout(layout)

    def load_data(self):
        """Load data from sheerIDlink.txt file."""
        base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_path, "sheerIDlink.txt")
        
        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", "sheerIDlink.txt does not exist")
            return

        with open(path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        self.table.setRowCount(0)
        self.vid_row_map = {}
        self.cb_select_all.setChecked(False)
        
        row = 0
        for line in lines:
            vid = self.extract_vid(line)
            if vid:
                self.table.insertRow(row)
                
                # Checkbox Item
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row, 0, chk_item)
                
                self.table.setItem(row, 1, QTableWidgetItem(vid))
                self.table.setItem(row, 2, QTableWidgetItem(line))
                self.table.setItem(row, 3, QTableWidgetItem("Ready"))
                self.table.setItem(row, 4, QTableWidgetItem(""))
                self.vid_row_map[vid] = row
                row += 1
    
    def toggle_select_all(self, state):
        """Toggle select all checkbox."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if state == Qt.CheckState.Checked.value:  # 2
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

    def extract_vid(self, line):
        """Extract verification ID from line."""
        m = re.search(r'verificationId=([a-zA-Z0-9]+)', line)
        if m:
            return m.group(1)
        m = re.search(r'verify/([a-zA-Z0-9]+)', line)
        if m:
            return m.group(1)
        return None

    def start_verify(self):
        """Start verification for selected items."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Notice", "Task is already running")
            return
            
        api_key = self.api_key_input.text().strip()
        links_data = []
        
        # Gather Checked Rows
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk.checkState() == Qt.CheckState.Checked:
                vid = self.table.item(row, 1).text()
                line = self.table.item(row, 2).text()
                
                # Optional: Filter out already success to prevent redundant calls?
                # User might want to re-check, so proceed.
                links_data.append({'vid': vid, 'line': line})
                
                self.table.setItem(row, 3, QTableWidgetItem("Pending"))
                self.table.setItem(row, 4, QTableWidgetItem("Waiting..."))

        if not links_data:
            QMessageBox.information(self, "Notice", "Please select items to verify first")
            return

        self.worker = VerifyWorker(api_key, links_data)
        self.worker.progress_signal.connect(self.update_row_status)
        self.worker.finished_signal.connect(lambda: [
            QMessageBox.information(self, "Complete", "Verification task finished"),
            self.btn_start.setEnabled(True),
            self.btn_start.setText("Verify Selected")
        ])
        self.worker.start()
        
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Verifying...")

    def update_row_status(self, data):
        """Update row status in table."""
        vid = data['vid']
        status = data['status']
        msg = data['msg']
        
        row = self.vid_row_map.get(vid)
        if row is not None:
            self.table.setItem(row, 3, QTableWidgetItem(status))
            self.table.setItem(row, 4, QTableWidgetItem(msg))
            
            # Colorize
            if status == "success":
                self.table.item(row, 3).setBackground(QColor("#d4edda"))
            elif status == "error" or "failed" in str(status).lower():
                self.table.item(row, 3).setBackground(QColor("#f8d7da"))
            elif status == "Processing" or status == "Running":
                self.table.item(row, 3).setBackground(QColor("#fff3cd"))

    def cancel_selected(self):
        """Cancel selected verification items."""
        checked_rows = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked:
                checked_rows.append(row)
                
        if not checked_rows:
            QMessageBox.warning(self, "Notice", "Please select rows to cancel")
            return
            
        reply = QMessageBox.question(
            self, "Confirm", 
            f"Are you sure you want to cancel {len(checked_rows)} task(s)?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for row in checked_rows:
                vid = self.table.item(row, 1).text()
                
                self.table.setItem(row, 4, QTableWidgetItem("Cancelling..."))
                
                res = self.verifier.cancel_verification(vid)
                
                msg = res.get("message", "Cancelled")
                self.table.setItem(row, 3, QTableWidgetItem("Cancelled"))
                self.table.setItem(row, 4, QTableWidgetItem(msg))

    def closeEvent(self, event):
        """Handle window close event."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = SheerIDWindow()
    win.show()
    sys.exit(app.exec())
