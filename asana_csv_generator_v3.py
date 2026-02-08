#!/usr/bin/env python3
"""
Asana CSV Generator V3 - Wizard-Based Workflow
Features:
- 6-step wizard for Kindle performance testing workflow
- Parent Task configuration (CRITICAL)
- Device-specific task filtering with Applicable column
- User-selectable BRD columns for Previous Value and Perf_BRD
- Smart data matching between template and BRD
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
                            QListWidgetItem, QHeaderView, QSplitter)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon, QColor


# ============================================================================
# CONSTANTS - Devices, Priorities, CSV Headers
# ============================================================================

DEVICES = [
    'Malbec', 'Cava', 'Barolo', 'Rossini', 'Sangria', 
    'Pisco', 'Seabreeze', 'Gibson', 'Paloma', 'Calvados',
    'Eanab', 'Decanter', 'All Devices'
]

PRIORITIES = [
    'P0', 'P1', 'P2', 'P3', 
    'OOBE', 'OOBE 1X',
    'GEN Ai',
    'HWR Existing', 'HWR New',
    'Keyboard Canvas', 'Color Stroke', 'HWR search', 'Q & A', 'NRS',
    'Raw OOBE', 'GPC New Feature', 'Double Tap'
]

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
# DATA MANAGER - Handles template and BRD file operations
# ============================================================================

class DataManager:
    """Handles template and BRD data loading and processing"""
    
    def __init__(self):
        self.template_data = None
        self.brd_data = None
        self.template_path = None
        self.brd_path = None
        
    def load_template(self, file_path):
        """Load task template from Excel or CSV"""
        try:
            logging.info(f"Loading template from: {file_path}")
            self.template_path = file_path
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.csv':
                df = pd.read_csv(file_path)
                sheet_name = Path(file_path).stem
                self.template_data = {sheet_name: df}
                return True, f"Loaded CSV: {len(df)} rows"
            elif file_ext in ['.xlsx', '.xls']:
                self.template_data = pd.read_excel(file_path, sheet_name=None)
                return True, f"Loaded {len(self.template_data)} sheets"
            else:
                return False, f"Unsupported format: {file_ext}"
                
        except Exception as e:
            logging.exception(f"Error loading template: {e}")
            return False, f"Error: {str(e)}"
            
    def load_brd(self, file_path):
        """Load BRD performance data"""
        try:
            logging.info(f"Loading BRD from: {file_path}")
            self.brd_path = file_path
            self.brd_data = pd.read_excel(file_path, sheet_name=None)
            return True, f"Loaded BRD: {len(self.brd_data)} sheets"
        except Exception as e:
            logging.exception(f"Error loading BRD: {e}")
            return False, f"Error: {str(e)}"
    
    def get_template_sheets(self):
        """Get list of sheet names from template"""
        if self.template_data:
            return list(self.template_data.keys())
        return []
    
    def get_brd_sheets(self):
        """Get list of sheet names from BRD"""
        if self.brd_data:
            return list(self.brd_data.keys())
        return []
    
    def get_brd_columns(self, sheet_name, device_filter=None):
        """Get columns from BRD sheet, filtered by device if specified"""
        if not self.brd_data or sheet_name not in self.brd_data:
            return []
        
        df = self.brd_data[sheet_name]
        all_columns = []
        device_columns = []
        brd_columns = []
        
        # Get device filter pattern
        device_pattern = device_filter.lower() if device_filter and device_filter != 'All Devices' else None
        
        for col in df.columns:
            col_str = str(col)
            
            # Skip 'Unnamed' columns - these are empty headers
            if col_str.startswith('Unnamed:') or col_str.startswith('Unnamed '):
                continue
            
            col_upper = col_str.upper()
            col_lower = col_str.lower()
            
            # Check if column matches device filter
            matches_device = False
            if device_pattern:
                if device_pattern in col_lower:
                    matches_device = True
            
            # Check if it's a BRD/Target column
            is_brd_column = 'BRD' in col_upper or 'TARGET' in col_upper
            
            # Also check first row for BRD/Target keywords
            if not is_brd_column and len(df) > 0:
                first_val = str(df.iloc[0][col]) if pd.notna(df.iloc[0][col]) else ''
                if 'BRD' in first_val.upper() or 'TARGET' in first_val.upper():
                    is_brd_column = True
            
            # Categorize columns
            if device_pattern and matches_device and is_brd_column:
                # Best match: device-specific BRD column
                device_columns.append(col_str)
            elif is_brd_column:
                brd_columns.append(col_str)
        
        # If device filter is set, prioritize device-specific columns
        if device_pattern and device_columns:
            return device_columns  # Only show device-specific columns
        elif brd_columns:
            return brd_columns  # Show all BRD columns if no device-specific found
        else:
            # Fallback: return non-Unnamed columns (first 20)
            for col in df.columns[:50]:
                col_str = str(col)
                if not col_str.startswith('Unnamed'):
                    all_columns.append(col_str)
            return all_columns[:20]
    
    def get_tasks_from_sheet(self, sheet_name, device=None, priorities=None):
        """Get filtered tasks from a template sheet"""
        if not self.template_data or sheet_name not in self.template_data:
            return []
        
        df = self.template_data[sheet_name]
        tasks = []
        
        for idx, row in df.iterrows():
            task = row.to_dict()
            
            # Filter by device if specified
            if device and device != 'All Devices':
                applicable = str(task.get('Applicable', '')).lower()
                applicable_devices = str(task.get('Applicable Devices', '')).lower()
                
                if applicable or applicable_devices:
                    combined = applicable + ' ' + applicable_devices
                    if device.lower() not in combined and 'all' not in combined:
                        continue
            
            # Filter by priority if specified
            if priorities:
                task_priority = str(task.get('Priority', '')).upper()
                if task_priority and task_priority not in [p.upper() for p in priorities]:
                    continue
            
            tasks.append(task)
        
        return tasks
    
    def match_brd_value(self, task_name, brd_sheet, column_name):
        """Find matching BRD value for a task"""
        if not self.brd_data or brd_sheet not in self.brd_data:
            return None
        
        df = self.brd_data[brd_sheet]
        task_name_lower = str(task_name).lower().strip()
        
        # Try to find matching row
        for idx, row in df.iterrows():
            # Check multiple possible name columns
            for name_col in ['Performance Scenario', 'Dashboard Scenario Name', 'Scenario Name', 'Name']:
                if name_col in row.index:
                    row_name = str(row[name_col]).lower().strip()
                    if task_name_lower in row_name or row_name in task_name_lower:
                        if column_name in row.index:
                            return row[column_name]
        
        return None


# ============================================================================
# WIZARD STEP WIDGETS
# ============================================================================

class Step1FileLoading(QWidget):
    """Step 1: Load Template and BRD files"""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("<h2>📁 Step 1: Load Files</h2>")
        layout.addWidget(title)
        
        info = QLabel("Load your template Excel (with test cases) and BRD Excel (with performance data).")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Template file
        template_group = QGroupBox("📋 Template File (Test Cases)")
        template_layout = QHBoxLayout(template_group)
        
        self.template_path_label = QLabel("No file selected")
        self.template_path_label.setStyleSheet("color: gray;")
        template_layout.addWidget(self.template_path_label, 1)
        
        self.load_template_btn = QPushButton("Browse...")
        self.load_template_btn.clicked.connect(self.load_template)
        template_layout.addWidget(self.load_template_btn)
        
        layout.addWidget(template_group)
        
        # Template info
        self.template_info = QLabel("")
        layout.addWidget(self.template_info)
        
        # BRD file
        brd_group = QGroupBox("📊 BRD File (Performance Data)")
        brd_layout = QHBoxLayout(brd_group)
        
        self.brd_path_label = QLabel("No file selected")
        self.brd_path_label.setStyleSheet("color: gray;")
        brd_layout.addWidget(self.brd_path_label, 1)
        
        self.load_brd_btn = QPushButton("Browse...")
        self.load_brd_btn.clicked.connect(self.load_brd)
        brd_layout.addWidget(self.load_brd_btn)
        
        layout.addWidget(brd_group)
        
        # BRD info
        self.brd_info = QLabel("")
        layout.addWidget(self.brd_info)
        
        layout.addStretch()
        
        # Auto-load BRD if present
        self.auto_load_brd()
        
    def auto_load_brd(self):
        """Auto-load BRD file if found in current directory"""
        current_dir = Path('.')
        brd_files = list(current_dir.glob('*Performance*.xlsx')) + list(current_dir.glob('*BRD*.xlsx'))
        
        if brd_files:
            success, message = self.data_manager.load_brd(str(brd_files[0]))
            if success:
                self.brd_path_label.setText(brd_files[0].name)
                self.brd_path_label.setStyleSheet("color: green; font-weight: bold;")
                self.brd_info.setText(f"✓ {message}")
                self.brd_info.setStyleSheet("color: green;")
        
    def load_template(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Template File", "",
            "Excel/CSV files (*.xlsx *.xls *.csv);;All files (*.*)")
        
        if file_path:
            success, message = self.data_manager.load_template(file_path)
            if success:
                self.template_path_label.setText(Path(file_path).name)
                self.template_path_label.setStyleSheet("color: green; font-weight: bold;")
                self.template_info.setText(f"✓ {message}")
                self.template_info.setStyleSheet("color: green;")
            else:
                QMessageBox.warning(self, "Error", message)
                
    def load_brd(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select BRD File", "",
            "Excel files (*.xlsx *.xls);;All files (*.*)")
        
        if file_path:
            success, message = self.data_manager.load_brd(file_path)
            if success:
                self.brd_path_label.setText(Path(file_path).name)
                self.brd_path_label.setStyleSheet("color: green; font-weight: bold;")
                self.brd_info.setText(f"✓ {message}")
                self.brd_info.setStyleSheet("color: green;")
            else:
                QMessageBox.warning(self, "Error", message)
                
    def is_valid(self):
        """Check if this step is complete"""
        return self.data_manager.template_data is not None


class Step2ParentTask(QWidget):
    """Step 2: Configure Parent Task (CRITICAL)"""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title with emphasis
        title = QLabel("<h2>⭐ Step 2: Configure Parent Task</h2>")
        layout.addWidget(title)
        
        warning = QLabel("<b style='color: #D32F2F;'>⚠️ CRITICAL: All test cases will be added as subtasks under this parent!</b>")
        layout.addWidget(warning)
        
        # Section Name
        section_group = QGroupBox("📋 Section Name")
        section_layout = QVBoxLayout(section_group)
        
        self.section_edit = QLineEdit()
        self.section_edit.setPlaceholderText("e.g., Week_05 J19.3")
        self.section_edit.setFont(QFont("Arial", 12))
        section_layout.addWidget(self.section_edit)
        
        layout.addWidget(section_group)
        
        # Parent Task Name
        parent_group = QGroupBox("👤 Parent Task Name")
        parent_layout = QVBoxLayout(parent_group)
        
        self.parent_edit = QLineEdit()
        self.parent_edit.setPlaceholderText("e.g., P1 Barolo")
        self.parent_edit.setFont(QFont("Arial", 14, QFont.Bold))
        self.parent_edit.textChanged.connect(self.update_preview)
        parent_layout.addWidget(self.parent_edit)
        
        # Quick select buttons
        quick_label = QLabel("💡 Quick Select:")
        parent_layout.addWidget(quick_label)
        
        quick_layout = QHBoxLayout()
        quick_options = ["P0 All Devices", "P1 Malbec", "P1 Barolo", "P2 Cava", "P3 Rossini"]
        for option in quick_options:
            btn = QPushButton(option)
            btn.clicked.connect(lambda checked, o=option: self.parent_edit.setText(o))
            btn.setStyleSheet("QPushButton { padding: 5px 10px; }")
            quick_layout.addWidget(btn)
        quick_layout.addStretch()
        parent_layout.addLayout(quick_layout)
        
        quick_layout2 = QHBoxLayout()
        quick_options2 = ["OOBE Gibson Standard", "Gen AI Pisco", "HWR Existing"]
        for option in quick_options2:
            btn = QPushButton(option)
            btn.clicked.connect(lambda checked, o=option: self.parent_edit.setText(o))
            btn.setStyleSheet("QPushButton { padding: 5px 10px; }")
            quick_layout2.addWidget(btn)
        quick_layout2.addStretch()
        parent_layout.addLayout(quick_layout2)
        
        layout.addWidget(parent_group)
        
        # Preview
        preview_group = QGroupBox("📌 Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("All imported tasks will be subtasks of: <i>(enter parent name above)</i>")
        self.preview_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #E8F5E9; border-radius: 5px;")
        preview_layout.addWidget(self.preview_label)
        
        layout.addWidget(preview_group)
        layout.addStretch()
        
    def update_preview(self, text):
        if text:
            self.preview_label.setText(f"All imported tasks will be subtasks of: <b>{text}</b>")
        else:
            self.preview_label.setText("All imported tasks will be subtasks of: <i>(enter parent name above)</i>")
    
    def get_data(self):
        return {
            'section_name': self.section_edit.text().strip(),
            'parent_task': self.parent_edit.text().strip()
        }
    
    def is_valid(self):
        return bool(self.section_edit.text().strip() and self.parent_edit.text().strip())


class Step3DevicePriority(QWidget):
    """Step 3: Select Device and Priority Sheet"""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("<h2>🎯 Step 3: Select Device & Priority Sheet</h2>")
        layout.addWidget(title)
        
        info = QLabel("""
            <p>Select the target device and priority sheet.</p>
            <p><b>Note:</b> Each sheet in your template represents a priority (P0, P1, P2, P3, OOBE, etc.)</p>
        """)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Device selection
        device_group = QGroupBox("📱 Target Device")
        device_layout = QVBoxLayout(device_group)
        
        self.device_combo = QComboBox()
        self.device_combo.addItems(DEVICES)
        self.device_combo.setCurrentText("Malbec")
        self.device_combo.setFont(QFont("Arial", 11))
        self.device_combo.currentTextChanged.connect(self.update_task_count)
        device_layout.addWidget(self.device_combo)
        
        layout.addWidget(device_group)
        
        # Priority Sheet selection (THIS IS THE KEY CHANGE)
        priority_group = QGroupBox("⚡ Priority Sheet (select the sheet containing your tasks)")
        priority_layout = QVBoxLayout(priority_group)
        
        priority_info = QLabel("<i>Each sheet = One Priority. Select the priority sheet you want to import.</i>")
        priority_info.setStyleSheet("color: #666;")
        priority_layout.addWidget(priority_info)
        
        self.sheet_combo = QComboBox()
        self.sheet_combo.setFont(QFont("Arial", 12, QFont.Bold))
        self.sheet_combo.setMinimumHeight(35)
        self.sheet_combo.currentTextChanged.connect(self.on_sheet_changed)
        priority_layout.addWidget(self.sheet_combo)
        
        # Show sheet info
        self.sheet_info = QLabel("")
        self.sheet_info.setStyleSheet("padding: 10px; background-color: #FFF3E0; border-radius: 5px;")
        priority_layout.addWidget(self.sheet_info)
        
        layout.addWidget(priority_group)
        
        # Available sheets list for quick reference
        sheets_group = QGroupBox("📋 All Available Priority Sheets")
        sheets_layout = QVBoxLayout(sheets_group)
        
        self.sheets_list = QListWidget()
        self.sheets_list.setMaximumHeight(150)
        self.sheets_list.itemClicked.connect(self.on_sheet_list_clicked)
        sheets_layout.addWidget(self.sheets_list)
        
        layout.addWidget(sheets_group)
        
        # Task count preview
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("font-size: 14px; color: #1976D2; padding: 10px; background-color: #E3F2FD; border-radius: 5px;")
        layout.addWidget(self.count_label)
        
        layout.addStretch()
        
    def refresh_sheets(self):
        """Refresh available sheets from template"""
        self.sheet_combo.clear()
        self.sheets_list.clear()
        
        sheets = self.data_manager.get_template_sheets()
        
        # Add sheets to combo and list
        for sheet in sheets:
            self.sheet_combo.addItem(sheet)
            self.sheets_list.addItem(sheet)
        
        if sheets:
            self.on_sheet_changed(sheets[0])
    
    def on_sheet_changed(self, sheet_name):
        """Update info when sheet selection changes"""
        if not sheet_name:
            return
        
        # Detect priority from sheet name
        priority = self.detect_priority(sheet_name)
        
        self.sheet_info.setText(
            f"📄 Selected Sheet: <b>{sheet_name}</b><br>"
            f"⚡ Detected Priority: <b>{priority}</b>"
        )
        
        self.update_task_count()
    
    def on_sheet_list_clicked(self, item):
        """Handle click on sheet list - select that sheet"""
        self.sheet_combo.setCurrentText(item.text())
    
    def detect_priority(self, sheet_name):
        """Detect priority from sheet name"""
        sheet_upper = sheet_name.upper()
        
        # Check for common priority patterns
        priority_map = {
            'P0': ['P0', 'P0_', 'P0 '],
            'P1': ['P1', 'P1_', 'P1 ', 'P1('],
            'P2': ['P2', 'P2_', 'P2 ', 'P2('],
            'P3': ['P3', 'P3_', 'P3 ', 'P3('],
            'OOBE': ['OOBE', 'RAW OOBE'],
            'GEN AI': ['GEN AI', 'GENAI', 'GEN_AI'],
            'HWR': ['HWR'],
            'CANVAS': ['CANVAS'],
            'GPC': ['GPC'],
        }
        
        for priority, patterns in priority_map.items():
            for pattern in patterns:
                if pattern in sheet_upper:
                    return priority
        
        return sheet_name  # Return sheet name if no pattern matched
    
    def update_task_count(self):
        """Update task count based on current selection"""
        sheet = self.sheet_combo.currentText()
        device = self.device_combo.currentText()
        
        if sheet and self.data_manager.template_data:
            # Get tasks filtered by device (no priority filter since sheet IS the priority)
            tasks = self.data_manager.get_tasks_from_sheet(sheet, device, None)
            priority = self.detect_priority(sheet)
            self.count_label.setText(
                f"📊 Found <b>{len(tasks)}</b> tasks in sheet <b>{sheet}</b> "
                f"for device <b>{device}</b> (Priority: {priority})"
            )
    
    def get_data(self):
        sheet_name = self.sheet_combo.currentText()
        priority = self.detect_priority(sheet_name)
        
        return {
            'device': self.device_combo.currentText(),
            'sheet': sheet_name,
            'priorities': [priority],  # Sheet name IS the priority
            'detected_priority': priority
        }
    
    def is_valid(self):
        return bool(self.sheet_combo.currentText())


class Step4BRDColumns(QWidget):
    """Step 4: Configure BRD Columns"""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.selected_device = None  # Store selected device from Step 3
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("<h2>📊 Step 4: Configure BRD Columns</h2>")
        layout.addWidget(title)
        
        info = QLabel("Select which columns from the BRD file to use for Perf_BRD and Previous Value.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Device info (passed from Step 3)
        self.device_info_label = QLabel("")
        self.device_info_label.setStyleSheet("padding: 10px; background-color: #E8F5E9; border-radius: 5px; font-weight: bold;")
        layout.addWidget(self.device_info_label)
        
        # BRD Sheet selection
        sheet_group = QGroupBox("📄 BRD Sheet")
        sheet_layout = QVBoxLayout(sheet_group)
        
        self.brd_sheet_combo = QComboBox()
        self.brd_sheet_combo.currentTextChanged.connect(self.on_sheet_changed)
        sheet_layout.addWidget(self.brd_sheet_combo)
        
        layout.addWidget(sheet_group)
        
        # Column selection
        columns_group = QGroupBox("📊 Column Selection (filtered for selected device)")
        columns_layout = QGridLayout(columns_group)
        
        columns_layout.addWidget(QLabel("Perf_BRD Column:"), 0, 0)
        self.perf_brd_combo = QComboBox()
        columns_layout.addWidget(self.perf_brd_combo, 0, 1)
        
        columns_layout.addWidget(QLabel("Previous Value Column:"), 1, 0)
        self.previous_combo = QComboBox()
        columns_layout.addWidget(self.previous_combo, 1, 1)
        
        layout.addWidget(columns_group)
        
        # Available columns list
        available_group = QGroupBox("📋 Available BRD Columns")
        available_layout = QVBoxLayout(available_group)
        
        self.columns_list = QListWidget()
        available_layout.addWidget(self.columns_list)
        
        # Column count label
        self.column_count_label = QLabel("")
        self.column_count_label.setStyleSheet("color: #666;")
        available_layout.addWidget(self.column_count_label)
        
        layout.addWidget(available_group)
        
        layout.addStretch()
    
    def set_device(self, device):
        """Set the device filter from Step 3"""
        self.selected_device = device
        self.device_info_label.setText(f"📱 Filtering columns for device: <b>{device}</b>")
        
    def refresh_brd_sheets(self, device=None):
        """Refresh BRD sheets from data manager"""
        if device:
            self.selected_device = device
            self.device_info_label.setText(f"📱 Filtering columns for device: <b>{device}</b>")
        
        self.brd_sheet_combo.clear()
        sheets = self.data_manager.get_brd_sheets()
        self.brd_sheet_combo.addItems(sheets)
        
    def on_sheet_changed(self, sheet_name):
        """Update column options when BRD sheet changes"""
        if not sheet_name:
            return
        
        # Pass device filter to get only relevant columns
        columns = self.data_manager.get_brd_columns(sheet_name, self.selected_device)
        
        # Update combos
        self.perf_brd_combo.clear()
        self.previous_combo.clear()
        self.perf_brd_combo.addItems(columns)
        self.previous_combo.addItems(columns)
        
        # Update list
        self.columns_list.clear()
        for col in columns:
            self.columns_list.addItem(col)
        
        # Update count label
        if self.selected_device and self.selected_device != 'All Devices':
            self.column_count_label.setText(
                f"Found {len(columns)} columns matching device '{self.selected_device}'"
            )
        else:
            self.column_count_label.setText(f"Found {len(columns)} BRD columns")
    
    def get_data(self):
        return {
            'brd_sheet': self.brd_sheet_combo.currentText(),
            'perf_brd_column': self.perf_brd_combo.currentText(),
            'previous_column': self.previous_combo.currentText()
        }
    
    def is_valid(self):
        return bool(self.brd_sheet_combo.currentText())


class Step5Preview(QWidget):
    """Step 5: Preview and Match Data"""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.tasks = []
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("<h2>👁️ Step 5: Preview & Match Data</h2>")
        layout.addWidget(title)
        
        # Summary info
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 14px; padding: 10px; background-color: #E3F2FD; border-radius: 5px;")
        layout.addWidget(self.summary_label)
        
        # Preview table
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(7)
        self.preview_table.setHorizontalHeaderLabels([
            "☑", "Task Name", "Priority", "Time", "Parent Task", "Perf_BRD", "Previous Value"
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.preview_table)
        
        # Controls
        controls = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        controls.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        controls.addWidget(deselect_all_btn)
        
        controls.addStretch()
        
        self.count_label = QLabel("0 tasks selected")
        controls.addWidget(self.count_label)
        
        layout.addLayout(controls)
        
    def load_preview(self, parent_data, device_priority_data, brd_data):
        """Load tasks into preview table"""
        self.preview_table.setRowCount(0)
        self.tasks = []
        
        # Get filtered tasks
        tasks = self.data_manager.get_tasks_from_sheet(
            device_priority_data['sheet'],
            device_priority_data['device'],
            device_priority_data['priorities']
        )
        
        self.summary_label.setText(
            f"📌 Parent: <b>{parent_data['parent_task']}</b> | "
            f"Section: <b>{parent_data['section_name']}</b> | "
            f"Device: <b>{device_priority_data['device']}</b> | "
            f"Found: <b>{len(tasks)} tasks</b>"
        )
        
        for task in tasks:
            row = self.preview_table.rowCount()
            self.preview_table.insertRow(row)
            
            # Checkbox
            cb = QCheckBox()
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_count)
            self.preview_table.setCellWidget(row, 0, cb)
            
            # Task name - try multiple columns
            task_name = ""
            for col in ['Performance Scenario', 'Scenario Name', 'Dashboard Scenario Name', 'Name', 'Task Name']:
                if col in task and pd.notna(task[col]):
                    task_name = str(task[col])
                    break
            self.preview_table.setItem(row, 1, QTableWidgetItem(task_name))
            
            # Priority
            priority = str(task.get('Priority', ''))
            self.preview_table.setItem(row, 2, QTableWidgetItem(priority))
            
            # Time
            time_val = task.get('Time', task.get('Estimated time', ''))
            self.preview_table.setItem(row, 3, QTableWidgetItem(str(time_val)))
            
            # Parent Task (from Step 2)
            self.preview_table.setItem(row, 4, QTableWidgetItem(parent_data['parent_task']))
            
            # BRD values
            perf_brd = self.data_manager.match_brd_value(
                task_name, brd_data['brd_sheet'], brd_data['perf_brd_column']
            )
            previous = self.data_manager.match_brd_value(
                task_name, brd_data['brd_sheet'], brd_data['previous_column']
            )
            
            self.preview_table.setItem(row, 5, QTableWidgetItem(str(perf_brd) if perf_brd else ""))
            self.preview_table.setItem(row, 6, QTableWidgetItem(str(previous) if previous else ""))
            
            self.tasks.append({
                'name': task_name,
                'priority': priority,
                'time': time_val,
                'parent_task': parent_data['parent_task'],
                'section': parent_data['section_name'],
                'perf_brd': perf_brd,
                'previous_value': previous,
                'notes': task.get('Notes', task.get('Performance Scenario', ''))
            })
        
        self.update_count()
        
    def select_all(self):
        for row in range(self.preview_table.rowCount()):
            cb = self.preview_table.cellWidget(row, 0)
            if cb:
                cb.setChecked(True)
                
    def deselect_all(self):
        for row in range(self.preview_table.rowCount()):
            cb = self.preview_table.cellWidget(row, 0)
            if cb:
                cb.setChecked(False)
                
    def update_count(self):
        count = 0
        for row in range(self.preview_table.rowCount()):
            cb = self.preview_table.cellWidget(row, 0)
            if cb and cb.isChecked():
                count += 1
        self.count_label.setText(f"{count} tasks selected")
        
    def get_selected_tasks(self):
        """Return list of selected tasks"""
        selected = []
        for row in range(self.preview_table.rowCount()):
            cb = self.preview_table.cellWidget(row, 0)
            if cb and cb.isChecked() and row < len(self.tasks):
                selected.append(self.tasks[row])
        return selected
    
    def is_valid(self):
        return len(self.get_selected_tasks()) > 0


class Step6Export(QWidget):
    """Step 6: Generate and Export CSV"""
    
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("<h2>✅ Step 6: Generate CSV</h2>")
        layout.addWidget(title)
        
        info = QLabel("Review the summary below and click Generate to create your Asana CSV file.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Summary
        summary_group = QGroupBox("📋 Export Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(200)
        summary_layout.addWidget(self.summary_text)
        
        layout.addWidget(summary_group)
        
        # Project name
        project_group = QGroupBox("📁 Project Name for Asana")
        project_layout = QVBoxLayout(project_group)
        
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("e.g., J19.2 SBR J19.3 Mainline")
        self.project_name_edit.setFont(QFont("Arial", 12))
        project_layout.addWidget(self.project_name_edit)
        
        layout.addWidget(project_group)
        
        # Generate button
        self.generate_btn = QPushButton("🚀 Generate Asana CSV")
        self.generate_btn.setFont(QFont("Arial", 14, QFont.Bold))
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 15px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
        """)
        layout.addWidget(self.generate_btn)
        
        # Result
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(self.result_label)
        
        layout.addStretch()
        
    def update_summary(self, parent_data, device_priority_data, tasks):
        """Update the summary text"""
        summary = f"""
📌 Section: {parent_data['section_name']}
👤 Parent Task: {parent_data['parent_task']}
📱 Device: {device_priority_data['device']}
⚡ Priorities: {', '.join(device_priority_data['priorities'])}
📄 Template Sheet: {device_priority_data['sheet']}

✅ Tasks to import: {len(tasks)}
"""
        self.summary_text.setPlainText(summary)


# ============================================================================
# MAIN WIZARD APPLICATION
# ============================================================================

class AsanaCSVGeneratorV3(QMainWindow):
    """Main application with 6-step wizard"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asana CSV Generator V3 - Wizard Workflow")
        self.setGeometry(100, 100, 1000, 750)
        
        self.data_manager = DataManager()
        self.current_step = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # Header with progress
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<h1>🚀 Asana CSV Generator</h1>"))
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # Step indicator
        self.step_labels = []
        steps_layout = QHBoxLayout()
        step_names = ["1. Files", "2. Parent", "3. Device", "4. BRD", "5. Preview", "6. Export"]
        
        for i, name in enumerate(step_names):
            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    padding: 10px 15px;
                    border-radius: 5px;
                    font-weight: bold;
                }
            """)
            self.step_labels.append(label)
            steps_layout.addWidget(label)
            
        main_layout.addLayout(steps_layout)
        
        # Stacked widget for steps
        self.step_stack = QStackedWidget()
        
        # Create steps
        self.step1 = Step1FileLoading(self.data_manager)
        self.step2 = Step2ParentTask(self.data_manager)
        self.step3 = Step3DevicePriority(self.data_manager)
        self.step4 = Step4BRDColumns(self.data_manager)
        self.step5 = Step5Preview(self.data_manager)
        self.step6 = Step6Export(self.data_manager)
        
        self.step_stack.addWidget(self.step1)
        self.step_stack.addWidget(self.step2)
        self.step_stack.addWidget(self.step3)
        self.step_stack.addWidget(self.step4)
        self.step_stack.addWidget(self.step5)
        self.step_stack.addWidget(self.step6)
        
        main_layout.addWidget(self.step_stack)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        self.back_btn = QPushButton("← Back")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setStyleSheet("QPushButton { padding: 10px 20px; }")
        nav_layout.addWidget(self.back_btn)
        
        nav_layout.addStretch()
        
        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self.go_next)
        self.next_btn.setStyleSheet("""
            QPushButton { 
                padding: 10px 30px; 
                background-color: #2196F3; 
                color: white; 
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        nav_layout.addWidget(self.next_btn)
        
        main_layout.addLayout(nav_layout)
        
        # Connect export button
        self.step6.generate_btn.clicked.connect(self.generate_csv)
        
        # Update initial state
        self.update_step_indicators()
        
    def update_step_indicators(self):
        """Update visual indicators for current step"""
        for i, label in enumerate(self.step_labels):
            if i < self.current_step:
                label.setStyleSheet("""
                    QLabel {
                        padding: 10px 15px;
                        border-radius: 5px;
                        font-weight: bold;
                        background-color: #C8E6C9;
                        color: #2E7D32;
                    }
                """)
            elif i == self.current_step:
                label.setStyleSheet("""
                    QLabel {
                        padding: 10px 15px;
                        border-radius: 5px;
                        font-weight: bold;
                        background-color: #2196F3;
                        color: white;
                    }
                """)
            else:
                label.setStyleSheet("""
                    QLabel {
                        padding: 10px 15px;
                        border-radius: 5px;
                        font-weight: bold;
                        background-color: #E0E0E0;
                        color: #757575;
                    }
                """)
        
        # Update button states
        self.back_btn.setEnabled(self.current_step > 0)
        self.next_btn.setText("Next →" if self.current_step < 5 else "Finish")
        
    def go_back(self):
        if self.current_step > 0:
            self.current_step -= 1
            self.step_stack.setCurrentIndex(self.current_step)
            self.update_step_indicators()
            
    def go_next(self):
        # Validate current step
        current_widget = self.step_stack.currentWidget()
        if hasattr(current_widget, 'is_valid') and not current_widget.is_valid():
            QMessageBox.warning(self, "Incomplete", "Please complete this step before proceeding.")
            return
        
        if self.current_step < 5:
            self.current_step += 1
            self.step_stack.setCurrentIndex(self.current_step)
            
            # Refresh data for certain steps
            if self.current_step == 2:  # Step 3 - Device/Priority
                self.step3.refresh_sheets()
            elif self.current_step == 3:  # Step 4 - BRD
                # Get selected device from Step 3 and pass to Step 4
                step3_data = self.step3.get_data()
                selected_device = step3_data.get('device', 'All Devices')
                self.step4.refresh_brd_sheets(selected_device)
            elif self.current_step == 4:  # Step 5 - Preview
                self.load_preview()
            elif self.current_step == 5:  # Step 6 - Export
                self.prepare_export()
                
            self.update_step_indicators()
            
    def load_preview(self):
        """Load preview data into Step 5"""
        parent_data = self.step2.get_data()
        device_priority_data = self.step3.get_data()
        brd_data = self.step4.get_data()
        
        self.step5.load_preview(parent_data, device_priority_data, brd_data)
        
    def prepare_export(self):
        """Prepare export summary in Step 6"""
        parent_data = self.step2.get_data()
        device_priority_data = self.step3.get_data()
        tasks = self.step5.get_selected_tasks()
        
        self.step6.update_summary(parent_data, device_priority_data, tasks)
        
    def generate_csv(self):
        """Generate the final CSV file"""
        tasks = self.step5.get_selected_tasks()
        if not tasks:
            QMessageBox.warning(self, "No Tasks", "No tasks selected for export.")
            return
            
        parent_data = self.step2.get_data()
        project_name = self.step6.project_name_edit.text().strip() or "Asana Import"
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"asana_import_{parent_data['parent_task'].replace(' ', '_')}_{timestamp}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", filename, "CSV files (*.csv)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_HEADERS)
                
                # Write section row
                section_row = [''] * len(CSV_HEADERS)
                section_row[4] = parent_data['section_name']  # Name
                section_row[5] = parent_data['section_name']  # Section/Column
                section_row[12] = project_name  # Projects
                writer.writerow(section_row)
                
                # Write parent task row
                parent_row = [''] * len(CSV_HEADERS)
                parent_row[4] = parent_data['parent_task']  # Name
                parent_row[5] = parent_data['section_name']  # Section/Column
                parent_row[12] = project_name  # Projects
                writer.writerow(parent_row)
                
                # Write task rows
                for task in tasks:
                    row = [''] * len(CSV_HEADERS)
                    row[4] = task['name']  # Name
                    row[5] = parent_data['section_name']  # Section/Column
                    row[11] = str(task.get('notes', ''))  # Notes
                    row[12] = project_name  # Projects
                    row[13] = parent_data['parent_task']  # Parent task
                    
                    # Time conversion
                    time_val = task.get('time', 15)
                    try:
                        time_minutes = int(float(str(time_val))) if time_val else 15
                        row[16] = f"{time_minutes//60}:{time_minutes%60:02d}"
                    except:
                        row[16] = "0:15"
                        
                    row[18] = task.get('priority', '')  # Priority
                    row[26] = str(task.get('perf_brd', '')) if task.get('perf_brd') else ''  # Perf_BRD
                    row[32] = str(task.get('previous_value', '')) if task.get('previous_value') else ''  # Previous Value
                    
                    writer.writerow(row)
                    
            self.step6.result_label.setText(f"✅ Successfully exported {len(tasks)} tasks to:\n{file_path}")
            self.step6.result_label.setStyleSheet("color: green; font-weight: bold;")
            
            QMessageBox.information(self, "Success", f"Exported {len(tasks)} tasks to:\n{file_path}")
            
        except Exception as e:
            logging.exception(f"Error generating CSV: {e}")
            self.step6.result_label.setText(f"❌ Error: {str(e)}")
            self.step6.result_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "Error", f"Failed to generate CSV:\n{str(e)}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = AsanaCSVGeneratorV3()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
