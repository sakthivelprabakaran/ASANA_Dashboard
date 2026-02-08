#!/usr/bin/env python3
"""
Asana CSV Generator V4 - Multi-Parent Task Builder
Features:
- Add multiple parent task configurations to a queue
- P0 "All Devices" mode: duplicate tasks with Device field per device
- P1/P2 mode: separate parent per device
- Export all configurations as single CSV
- Auto-populate Devices field for Asana filtering
"""

import sys
import csv
from datetime import datetime
import pandas as pd
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('asana_generator.log'),
        logging.StreamHandler()
    ]
)

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QLabel, QLineEdit, 
                            QTextEdit, QComboBox, QSpinBox, QPushButton, 
                            QTableWidget, QTableWidgetItem, QStackedWidget,
                            QGroupBox, QFileDialog, QMessageBox, QTreeWidget,
                            QTreeWidgetItem, QCheckBox, QScrollArea, QFrame,
                            QProgressBar, QRadioButton, QButtonGroup, QListWidget,
                            QListWidgetItem, QHeaderView, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QColor


# ============================================================================
# CONSTANTS
# ============================================================================

DEVICES = [
    'Malbec', 'Cava', 'Barolo', 'Rossini', 'Sangria', 
    'Pisco', 'Seabreeze', 'Gibson', 'Paloma', 'Calvados',
    'Eanab', 'Decanter'
]

ALL_DEVICES_OPTION = 'All Devices (Duplicate per device)'

CSV_HEADERS = [
    "Task ID", "Created At", "Completed At", "Last Modified", "Name", 
    "Section/Column", "Assignee", "Assignee Email", "Start Date", "Due Date", 
    "Tags", "Notes", "Projects", "Parent task", "Blocked By (Dependencies)", 
    "Blocking (Dependencies)", "Estimated time", "Actual time", "Priority", 
    "Task Progress", "Iteration_01", "Iteration_02", "Iteration_03", 
    "Iteration_04", "iteration_05", "Average", "Perf_BRD", 
    "Deviation % Current Vs BRD", "GREEN", "YELLOW", "RED", "Devices", 
    "Previous Value", "BRD Status", "Deviation % Current vs Previous", 
    "Previous Status", "Tester Remark", "Logs Link", "Audited By", 
    "Auditor N-points elapsed time (h:m)", "DA Value", "Auditor Pass", 
    "iteration_06", "iteration_07", "iteration_08", "iteration_09", 
    "iteration_10", "Iteration count"
]


# ============================================================================
# DATA MANAGER
# ============================================================================

class DataManager:
    """Handles template and BRD data"""
    
    def __init__(self):
        self.template_data = None
        self.brd_data = None
        self.template_path = None
        self.brd_path = None
        
    def load_template(self, file_path):
        try:
            self.template_path = file_path
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.csv':
                df = pd.read_csv(file_path)
                self.template_data = {Path(file_path).stem: df}
                return True, f"CSV: {len(df)} rows"
            elif file_ext in ['.xlsx', '.xls']:
                self.template_data = pd.read_excel(file_path, sheet_name=None)
                return True, f"{len(self.template_data)} sheets"
            return False, "Unsupported format"
        except Exception as e:
            return False, str(e)
            
    def load_brd(self, file_path):
        try:
            self.brd_path = file_path
            self.brd_data = pd.read_excel(file_path, sheet_name=None)
            return True, f"{len(self.brd_data)} sheets"
        except Exception as e:
            return False, str(e)
    
    def get_template_sheets(self):
        return list(self.template_data.keys()) if self.template_data else []
    
    def get_brd_sheets(self):
        return list(self.brd_data.keys()) if self.brd_data else []
    
    def get_brd_columns(self, sheet_name, device_filter=None):
        """Get BRD columns, filtered by device if specified"""
        if not self.brd_data or sheet_name not in self.brd_data:
            return []
        
        df = self.brd_data[sheet_name]
        device_columns = []
        brd_columns = []
        device_pattern = device_filter.lower() if device_filter else None
        
        for col in df.columns:
            col_str = str(col)
            if col_str.startswith('Unnamed'):
                continue
            
            col_upper = col_str.upper()
            col_lower = col_str.lower()
            
            is_brd = 'BRD' in col_upper or 'TARGET' in col_upper
            if not is_brd and len(df) > 0:
                first_val = str(df.iloc[0][col]) if pd.notna(df.iloc[0][col]) else ''
                is_brd = 'BRD' in first_val.upper() or 'TARGET' in first_val.upper()
            
            if device_pattern and device_pattern in col_lower and is_brd:
                device_columns.append(col_str)
            elif is_brd:
                brd_columns.append(col_str)
        
        return device_columns if device_columns else brd_columns[:20]
    
    def get_tasks_from_sheet(self, sheet_name, device=None):
        """Get tasks from template sheet, filtered by device"""
        if not self.template_data or sheet_name not in self.template_data:
            return []
        
        df = self.template_data[sheet_name]
        tasks = []
        
        for _, row in df.iterrows():
            task = row.to_dict()
            
            # Skip if device filter and task not applicable
            if device and device not in [ALL_DEVICES_OPTION, 'All Devices']:
                applicable = str(task.get('Applicable', '')).lower()
                applicable_devices = str(task.get('Applicable Devices', '')).lower()
                combined = applicable + ' ' + applicable_devices
                
                if combined.strip() and device.lower() not in combined and 'all' not in combined:
                    continue
            
            tasks.append(task)
        
        return tasks
    
    def match_brd_value(self, task_name, brd_sheet, column_name):
        """Find matching BRD value for a task"""
        if not self.brd_data or brd_sheet not in self.brd_data:
            return None
        
        df = self.brd_data[brd_sheet]
        task_name_lower = str(task_name).lower().strip()
        
        for _, row in df.iterrows():
            for name_col in ['Performance Scenario', 'Dashboard Scenario Name', 'Scenario Name', 'Name']:
                if name_col in row.index:
                    row_name = str(row[name_col]).lower().strip()
                    if task_name_lower in row_name or row_name in task_name_lower:
                        if column_name in row.index:
                            return row[column_name]
        return None


# ============================================================================
# TASK CONFIGURATION
# ============================================================================

class TaskConfiguration:
    """Represents one parent task configuration"""
    
    def __init__(self):
        self.section_name = ""
        self.parent_task = ""
        self.device = ""
        self.is_all_devices = False
        self.sheet = ""
        self.brd_sheet = ""
        self.perf_brd_column = ""
        self.previous_column = ""
        self.task_count = 0
        
    def to_display_string(self):
        device_info = "All Devices" if self.is_all_devices else self.device
        return f"{self.parent_task} | {device_info} | {self.sheet} | {self.task_count} tasks"


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class AsanaCSVGeneratorV4(QMainWindow):
    """Multi-Parent Task Builder"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asana CSV Generator V4 - Multi-Parent Task Builder")
        self.setGeometry(100, 100, 1400, 850)
        
        self.data_manager = DataManager()
        self.configuration_queue = []  # List of TaskConfiguration
        
        self.setup_ui()
        self.auto_load_files()
        
    def auto_load_files(self):
        """Auto-load BRD file if found"""
        current_dir = Path('.')
        brd_files = list(current_dir.glob('*Performance*.xlsx')) + list(current_dir.glob('*BRD*.xlsx'))
        if brd_files:
            success, msg = self.data_manager.load_brd(str(brd_files[0]))
            if success:
                self.brd_label.setText(f"✓ {brd_files[0].name}")
                self.brd_label.setStyleSheet("color: green; font-weight: bold;")
                self.refresh_brd_sheets()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Header
        header = QLabel("<h1>🚀 Asana CSV Generator V4 - Multi-Parent Task Builder</h1>")
        main_layout.addWidget(header)
        
        # Main content area - horizontal splitter
        content_splitter = QSplitter(Qt.Horizontal)
        
        # ===== LEFT PANEL: File Loading =====
        left_panel = QGroupBox("📁 Files")
        left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        
        # Template file
        left_layout.addWidget(QLabel("<b>Template File:</b>"))
        self.template_label = QLabel("Not loaded")
        self.template_label.setStyleSheet("color: gray;")
        left_layout.addWidget(self.template_label)
        
        load_template_btn = QPushButton("📂 Load Template")
        load_template_btn.clicked.connect(self.load_template)
        left_layout.addWidget(load_template_btn)
        
        left_layout.addSpacing(10)
        
        # BRD file
        left_layout.addWidget(QLabel("<b>BRD File:</b>"))
        self.brd_label = QLabel("Not loaded")
        self.brd_label.setStyleSheet("color: gray;")
        left_layout.addWidget(self.brd_label)
        
        load_brd_btn = QPushButton("📊 Load BRD")
        load_brd_btn.clicked.connect(self.load_brd)
        left_layout.addWidget(load_brd_btn)
        
        left_layout.addStretch()
        
        # Project settings
        left_layout.addWidget(QLabel("<b>Project Name:</b>"))
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("e.g., J19.3 Mainline")
        left_layout.addWidget(self.project_name_edit)
        
        left_layout.addWidget(QLabel("<b>Section Name:</b>"))
        self.section_name_edit = QLineEdit()
        self.section_name_edit.setPlaceholderText("e.g., Week_05 J19.3")
        left_layout.addWidget(self.section_name_edit)
        
        content_splitter.addWidget(left_panel)
        
        # ===== CENTER PANEL: Configuration Builder =====
        center_panel = QGroupBox("⚙️ Add Configuration")
        center_layout = QVBoxLayout(center_panel)
        
        # Parent Task Name
        center_layout.addWidget(QLabel("<b>Parent Task Name:</b>"))
        self.parent_task_edit = QLineEdit()
        self.parent_task_edit.setPlaceholderText("e.g., P0 All Devices or P1 Malbec")
        self.parent_task_edit.setFont(QFont("Arial", 12, QFont.Bold))
        center_layout.addWidget(self.parent_task_edit)
        
        # Quick buttons
        quick_layout = QHBoxLayout()
        for name in ["P0 All Devices", "P1", "P2", "P3", "OOBE"]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda c, n=name: self.parent_task_edit.setText(n))
            quick_layout.addWidget(btn)
        center_layout.addLayout(quick_layout)
        
        # Device Selection
        center_layout.addWidget(QLabel("<b>Device:</b>"))
        self.device_combo = QComboBox()
        self.device_combo.addItem(ALL_DEVICES_OPTION)
        self.device_combo.addItems(DEVICES)
        self.device_combo.currentTextChanged.connect(self.on_device_changed)
        center_layout.addWidget(self.device_combo)
        
        # Info about All Devices
        self.all_devices_info = QLabel("⚠️ Tasks will be duplicated for EACH device with Device field set")
        self.all_devices_info.setStyleSheet("color: #D32F2F; font-style: italic;")
        center_layout.addWidget(self.all_devices_info)
        
        # Priority Sheet
        center_layout.addWidget(QLabel("<b>Priority Sheet:</b>"))
        self.sheet_combo = QComboBox()
        self.sheet_combo.currentTextChanged.connect(self.on_sheet_changed)
        center_layout.addWidget(self.sheet_combo)
        
        # BRD Sheet
        center_layout.addWidget(QLabel("<b>BRD Sheet:</b>"))
        self.brd_sheet_combo = QComboBox()
        self.brd_sheet_combo.currentTextChanged.connect(self.on_brd_sheet_changed)
        center_layout.addWidget(self.brd_sheet_combo)
        
        # BRD Columns
        brd_grid = QGridLayout()
        brd_grid.addWidget(QLabel("Perf_BRD:"), 0, 0)
        self.perf_brd_combo = QComboBox()
        brd_grid.addWidget(self.perf_brd_combo, 0, 1)
        brd_grid.addWidget(QLabel("Previous Value:"), 1, 0)
        self.previous_combo = QComboBox()
        brd_grid.addWidget(self.previous_combo, 1, 1)
        center_layout.addLayout(brd_grid)
        
        # Task count preview
        self.task_count_label = QLabel("")
        self.task_count_label.setStyleSheet("font-size: 14px; color: #1976D2; padding: 10px; background-color: #E3F2FD;")
        center_layout.addWidget(self.task_count_label)
        
        # Add to queue button
        add_btn = QPushButton("➕ Add to Queue")
        add_btn.setFont(QFont("Arial", 12, QFont.Bold))
        add_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 12px; }")
        add_btn.clicked.connect(self.add_to_queue)
        center_layout.addWidget(add_btn)
        
        center_layout.addStretch()
        content_splitter.addWidget(center_panel)
        
        # ===== RIGHT PANEL: Queue =====
        right_panel = QGroupBox("📋 Task Queue")
        right_layout = QVBoxLayout(right_panel)
        
        self.queue_list = QListWidget()
        self.queue_list.setFont(QFont("Arial", 11))
        right_layout.addWidget(self.queue_list)
        
        # Queue controls
        queue_controls = QHBoxLayout()
        remove_btn = QPushButton("🗑️ Remove Selected")
        remove_btn.clicked.connect(self.remove_from_queue)
        queue_controls.addWidget(remove_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_queue)
        queue_controls.addWidget(clear_btn)
        right_layout.addLayout(queue_controls)
        
        # Total summary
        self.total_label = QLabel("Total: 0 configurations, 0 tasks")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        right_layout.addWidget(self.total_label)
        
        # Export button
        export_btn = QPushButton("🚀 Export All to CSV")
        export_btn.setFont(QFont("Arial", 14, QFont.Bold))
        export_btn.setStyleSheet("""
            QPushButton { 
                background-color: #2196F3; 
                color: white; 
                padding: 15px; 
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        export_btn.clicked.connect(self.export_all)
        right_layout.addWidget(export_btn)
        
        content_splitter.addWidget(right_panel)
        
        # Set splitter sizes
        content_splitter.setSizes([250, 500, 400])
        main_layout.addWidget(content_splitter)
    
    # ===== FILE LOADING =====
    
    def load_template(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Template", "", "Excel/CSV (*.xlsx *.xls *.csv)")
        if file_path:
            success, msg = self.data_manager.load_template(file_path)
            if success:
                self.template_label.setText(f"✓ {Path(file_path).name}")
                self.template_label.setStyleSheet("color: green; font-weight: bold;")
                self.refresh_sheets()
            else:
                QMessageBox.warning(self, "Error", msg)
                
    def load_brd(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select BRD", "", "Excel (*.xlsx *.xls)")
        if file_path:
            success, msg = self.data_manager.load_brd(file_path)
            if success:
                self.brd_label.setText(f"✓ {Path(file_path).name}")
                self.brd_label.setStyleSheet("color: green; font-weight: bold;")
                self.refresh_brd_sheets()
            else:
                QMessageBox.warning(self, "Error", msg)
    
    def refresh_sheets(self):
        self.sheet_combo.clear()
        self.sheet_combo.addItems(self.data_manager.get_template_sheets())
        
    def refresh_brd_sheets(self):
        self.brd_sheet_combo.clear()
        self.brd_sheet_combo.addItems(self.data_manager.get_brd_sheets())
    
    # ===== EVENT HANDLERS =====
    
    def on_device_changed(self, device):
        is_all = device == ALL_DEVICES_OPTION
        self.all_devices_info.setVisible(is_all)
        self.update_task_count()
        self.update_brd_columns()
        
    def on_sheet_changed(self, sheet):
        self.update_task_count()
        
    def on_brd_sheet_changed(self, sheet):
        self.update_brd_columns()
        
    def update_brd_columns(self):
        sheet = self.brd_sheet_combo.currentText()
        device = self.device_combo.currentText()
        if device == ALL_DEVICES_OPTION:
            device = None
        
        columns = self.data_manager.get_brd_columns(sheet, device)
        self.perf_brd_combo.clear()
        self.previous_combo.clear()
        self.perf_brd_combo.addItems(columns)
        self.previous_combo.addItems(columns)
        
    def update_task_count(self):
        sheet = self.sheet_combo.currentText()
        device = self.device_combo.currentText()
        
        if not sheet:
            return
        
        is_all = device == ALL_DEVICES_OPTION
        tasks = self.data_manager.get_tasks_from_sheet(sheet, None if is_all else device)
        
        if is_all:
            total = len(tasks) * len(DEVICES)
            self.task_count_label.setText(
                f"📊 {len(tasks)} tasks × {len(DEVICES)} devices = <b>{total} total tasks</b>"
            )
        else:
            self.task_count_label.setText(f"📊 Found <b>{len(tasks)} tasks</b> for {device}")
    
    # ===== QUEUE MANAGEMENT =====
    
    def add_to_queue(self):
        # Validate
        if not self.parent_task_edit.text().strip():
            QMessageBox.warning(self, "Error", "Please enter a Parent Task name")
            return
        if not self.sheet_combo.currentText():
            QMessageBox.warning(self, "Error", "Please select a Priority Sheet")
            return
            
        config = TaskConfiguration()
        config.section_name = self.section_name_edit.text().strip()
        config.parent_task = self.parent_task_edit.text().strip()
        config.device = self.device_combo.currentText()
        config.is_all_devices = config.device == ALL_DEVICES_OPTION
        config.sheet = self.sheet_combo.currentText()
        config.brd_sheet = self.brd_sheet_combo.currentText()
        config.perf_brd_column = self.perf_brd_combo.currentText()
        config.previous_column = self.previous_combo.currentText()
        
        # Calculate task count
        tasks = self.data_manager.get_tasks_from_sheet(config.sheet, None if config.is_all_devices else config.device)
        config.task_count = len(tasks) * len(DEVICES) if config.is_all_devices else len(tasks)
        
        self.configuration_queue.append(config)
        self.queue_list.addItem(config.to_display_string())
        self.update_total()
        
        # Clear parent task for next entry
        self.parent_task_edit.clear()
        
    def remove_from_queue(self):
        row = self.queue_list.currentRow()
        if row >= 0:
            self.queue_list.takeItem(row)
            del self.configuration_queue[row]
            self.update_total()
            
    def clear_queue(self):
        self.queue_list.clear()
        self.configuration_queue.clear()
        self.update_total()
        
    def update_total(self):
        total_tasks = sum(c.task_count for c in self.configuration_queue)
        self.total_label.setText(
            f"Total: {len(self.configuration_queue)} configurations, {total_tasks} tasks"
        )
    
    # ===== EXPORT =====
    
    def export_all(self):
        if not self.configuration_queue:
            QMessageBox.warning(self, "Error", "No configurations in queue!")
            return
            
        project_name = self.project_name_edit.text().strip() or "Asana Import"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"asana_import_{timestamp}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", filename, "CSV (*.csv)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
                
                total_tasks = 0
                
                for config in self.configuration_queue:
                    section = config.section_name or "Section"
                    
                    # Write section row
                    section_row = [''] * len(CSV_HEADERS)
                    section_row[4] = section  # Name
                    section_row[5] = section  # Section/Column
                    section_row[12] = project_name
                    writer.writerow(section_row)
                    
                    # Write parent task row
                    parent_row = [''] * len(CSV_HEADERS)
                    parent_row[4] = config.parent_task  # Name
                    parent_row[5] = section  # Section/Column
                    parent_row[12] = project_name
                    writer.writerow(parent_row)
                    
                    # Get tasks
                    tasks = self.data_manager.get_tasks_from_sheet(
                        config.sheet, 
                        None if config.is_all_devices else config.device
                    )
                    
                    # Determine which devices to loop through
                    if config.is_all_devices:
                        devices_to_process = DEVICES
                    else:
                        devices_to_process = [config.device]
                    
                    # Write task rows
                    for device in devices_to_process:
                        for task in tasks:
                            # Get task name
                            task_name = ""
                            for col in ['Performance Scenario', 'Scenario Name', 'Dashboard Scenario Name', 'Name', 'Task Name']:
                                if col in task and pd.notna(task[col]):
                                    task_name = str(task[col])
                                    break
                            
                            if not task_name:
                                continue
                                
                            row = [''] * len(CSV_HEADERS)
                            row[4] = task_name  # Name
                            row[5] = section  # Section/Column
                            row[11] = str(task.get('Notes', task.get('Performance Scenario', '')))[:500]  # Notes
                            row[12] = project_name  # Projects
                            row[13] = config.parent_task  # Parent task
                            
                            # Time
                            time_val = task.get('Time', task.get('Estimated time', 15))
                            try:
                                time_min = int(float(str(time_val))) if time_val else 15
                                row[16] = f"{time_min//60}:{time_min%60:02d}"
                            except:
                                row[16] = "0:15"
                            
                            # Priority (from sheet name)
                            row[18] = config.sheet.split('(')[0].strip()
                            
                            # BRD values
                            perf_brd = self.data_manager.match_brd_value(
                                task_name, config.brd_sheet, config.perf_brd_column
                            )
                            previous = self.data_manager.match_brd_value(
                                task_name, config.brd_sheet, config.previous_column
                            )
                            
                            row[26] = str(perf_brd) if perf_brd else ""  # Perf_BRD
                            row[31] = device  # Devices field - AUTO POPULATED
                            row[32] = str(previous) if previous else ""  # Previous Value
                            
                            writer.writerow(row)
                            total_tasks += 1
                
            QMessageBox.information(
                self, "Success", 
                f"Exported {total_tasks} tasks from {len(self.configuration_queue)} configurations!\n\nFile: {file_path}"
            )
            
        except Exception as e:
            logging.exception(f"Export error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = AsanaCSVGeneratorV4()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
