"""
Asana CSV Generator v4.1 - Desktop Application
Full feature parity with web application.
Senior Developer perspective: Clean UX, web app terminology, intelligent matching.
"""

import os
import json
import logging
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, 
                             QComboBox, QTableView, QHeaderView, QMessageBox, QGroupBox, 
                             QScrollArea, QSplitter, QFrame, QListWidget, QListWidgetItem,
                             QTextEdit, QAbstractItemView, QMenu, QAction, QTabWidget)
from PyQt5.QtCore import Qt, QAbstractTableModel
from PyQt5.QtGui import QColor, QFont

from core.data_loader import DataLoader
from core.brd_matcher import BrdMatcher
from core.config_manager import ConfigManager
from ui.brd_viewer_dialog import BrdViewerDialog
from ui.report_generator_tab import ReportGeneratorTab
from ui.manual_subtask_dialog import ManualSubtaskDialog

logger = logging.getLogger('AsanaGenerator.MainWindow')


class TaskTableModel(QAbstractTableModel):
    """Table model for displaying task preview data."""
    
    def __init__(self, data, columns=None):
        super().__init__()
        self._data = data
        self._columns = columns or (list(data[0].keys()) if data else [])

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid() and role == Qt.DisplayRole:
            row_data = self._data[index.row()]
            col_key = self._columns[index.column()]
            val = row_data.get(col_key, '')
            return str(val)[:100]
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < len(self._columns):
                return self._columns[section]
        return None


class MainWindow(QMainWindow):
    """
    Main application window with full web app feature parity.
    Uses web app terminology for better UX.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asana CSV Generator")
        self.setGeometry(100, 100, 1400, 900)
        
        # Default template file path
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.default_template_path = os.path.join(app_dir, 'resources', 'Template.xlsx')
        
        # State - matching web app variable names
        self.templateSheets = {}          # {sheet_name: DataFrame}
        self.brdSheets = {}               # {sheet_name: List[List[Any]]} - raw data
        self.brdFilePath = None
        self.templateFilePath = None
        
        # Column selection from BRD viewer
        self.selectedPerfCol = {"name": "", "columnIndex": -1}
        self.selectedPrevCol = {"name": "", "columnIndex": -1}
        
        # Configuration queue - like web app's configQueue
        self.configQueue = []
        self.queue_file = os.path.join(os.path.expanduser('~'), '.asana_queue.json')
        
        # Config Manager (singleton)
        self.config = ConfigManager()
        
        # BRD Matcher
        self.brdMatcher = BrdMatcher()
        
        # Manual subtasks (ad-hoc testing) - persists in memory during session
        self.manualSubtasks = []  # List of {"name": str, "priority": str, "est_time": str}
        
        # UI Setup
        self.init_ui()
        self.load_styles()
        
        # Auto-load default template if it exists
        self._load_default_template()
        
        # Load saved queue
        self._load_queue_from_file()

    def load_styles(self):
        """Load QSS stylesheet."""
        style_paths = [
            os.path.join(os.path.dirname(__file__), "styles.qss"),
            "asana_generator_app/ui/styles.qss",
            "ui/styles.qss"
        ]
        for path in style_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        self.setStyleSheet(f.read())
                    return
                except:
                    continue
        print("Warning: Could not load stylesheet")

    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === HEADER (Light Theme) ===
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("""
            background-color: #ffffff; 
            border-bottom: 1px solid #e2e8f0;
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title = QLabel("⚡ Asana CSV Generator")
        title.setStyleSheet("""
            color: #3b82f6; 
            font-size: 18px; 
            font-weight: bold;
        """)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Profile selector in header
        header_layout.addWidget(QLabel("Profile:"))
        self.combo_profile = QComboBox()
        self.combo_profile.setMinimumWidth(180)
        self.combo_profile.setStyleSheet("padding: 4px 8px; font-size: 12px; font-weight: bold;")
        self._populate_profile_dropdown()
        self.combo_profile.currentTextChanged.connect(self._on_profile_changed)
        header_layout.addWidget(self.combo_profile)
        
        header_layout.addSpacing(16)
        
        self.lbl_status = QLabel("Ready - Load files to begin")
        self.lbl_status.setObjectName("status")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        header_layout.addWidget(self.lbl_status)
        
        main_layout.addWidget(header)

        # === TAB WIDGET ===
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #64748b;
                padding: 10px 24px;
                margin-right: 2px;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-bottom: 3px solid transparent;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #3b82f6;
                border-bottom: 3px solid #3b82f6;
            }
            QTabBar::tab:hover {
                background-color: #e2e8f0;
                color: #1e293b;
            }
        """)
        main_layout.addWidget(self.tab_widget)

        # === TAB 1: TASK CREATOR ===
        task_creator_tab = QWidget()
        task_creator_layout = QVBoxLayout(task_creator_tab)
        task_creator_layout.setContentsMargins(0, 0, 0, 0)
        task_creator_layout.setSpacing(0)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #e2e8f0; }")
        task_creator_layout.addWidget(splitter)

        # --- LEFT PANEL (Compact Sidebar) ---
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(300)
        left_scroll.setMaximumWidth(320)
        left_widget = QWidget()
        left_widget.setObjectName("sidebar")
        left_widget.setStyleSheet("background-color: #f8fafc;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_scroll.setWidget(left_widget)
        splitter.addWidget(left_scroll)

        # === MODE TOGGLE ===
        mode_frame = QFrame()
        mode_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        mode_inner = QHBoxLayout(mode_frame)
        mode_inner.setContentsMargins(6, 6, 6, 6)
        mode_inner.setSpacing(4)
        
        self.btn_template_mode = QPushButton("📄 Template")
        self.btn_template_mode.setCursor(Qt.PointingHandCursor)
        self.btn_template_mode.setCheckable(True)
        self.btn_template_mode.setChecked(True)
        self.btn_template_mode.clicked.connect(lambda: self._set_mode('template'))
        self.btn_template_mode.setStyleSheet("""
            QPushButton { padding: 8px 12px; border-radius: 4px; font-weight: bold; font-size: 12px; background: #3b82f6; color: white; border: none; }
            QPushButton:!checked { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }
        """)
        mode_inner.addWidget(self.btn_template_mode, 1)
        
        self.btn_manual_mode = QPushButton("🔧 Manual")
        self.btn_manual_mode.setCursor(Qt.PointingHandCursor)
        self.btn_manual_mode.setCheckable(True)
        self.btn_manual_mode.setChecked(False)
        self.btn_manual_mode.clicked.connect(lambda: self._set_mode('manual'))
        self.btn_manual_mode.setStyleSheet("""
            QPushButton { padding: 8px 12px; border-radius: 4px; font-weight: bold; font-size: 12px; background: #f59e0b; color: white; border: none; }
            QPushButton:!checked { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }
        """)
        mode_inner.addWidget(self.btn_manual_mode, 1)
        
        left_layout.addWidget(mode_frame)

        # === STEP 1: Load Files (Compact) ===
        self.step1_label = QLabel("STEP 1: FILES")
        self.step1_label.setObjectName("stepLabel")
        self.step1_label.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        left_layout.addWidget(self.step1_label)
        
        # Template file - compact inline
        self.tmpl_frame = QFrame()
        tmpl_frame = self.tmpl_frame
        tmpl_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;")
        tmpl_inner = QVBoxLayout(tmpl_frame)
        tmpl_inner.setContentsMargins(10, 8, 10, 8)
        tmpl_inner.setSpacing(6)
        
        tmpl_row1 = QHBoxLayout()
        tmpl_row1.addWidget(QLabel("📄 Template:"))
        self.btn_template = QPushButton("Update...")
        self.btn_template.setObjectName("fileUpload")
        self.btn_template.clicked.connect(self.load_template)
        self.btn_template.setCursor(Qt.PointingHandCursor)
        self.btn_template.setMaximumWidth(100)
        self.btn_template.setStyleSheet("padding: 6px 12px; font-size: 11px; background-color: #3b82f6; color: white; border-radius: 4px;")
        tmpl_row1.addStretch()
        tmpl_row1.addWidget(self.btn_template)
        tmpl_inner.addLayout(tmpl_row1)
        
        self.lbl_template = QLabel("No file loaded")
        self.lbl_template.setObjectName("filenameEmpty")
        self.lbl_template.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_template.setWordWrap(True)
        tmpl_inner.addWidget(self.lbl_template)
        
        # Template sheet selector
        tmpl_sheet_row = QHBoxLayout()
        tmpl_sheet_row.addWidget(QLabel("Sheet:"))
        self.combo_template_sheet = QComboBox()
        self.combo_template_sheet.setPlaceholderText("Select...")
        tmpl_sheet_row.addWidget(self.combo_template_sheet, 1)
        tmpl_inner.addLayout(tmpl_sheet_row)
        
        left_layout.addWidget(self.tmpl_frame)
        
        # BRD file - compact inline
        self.brd_frame = QFrame()
        brd_frame = self.brd_frame
        brd_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;")
        brd_inner = QVBoxLayout(brd_frame)
        brd_inner.setContentsMargins(10, 8, 10, 8)
        brd_inner.setSpacing(6)
        
        brd_row1 = QHBoxLayout()
        brd_row1.addWidget(QLabel("📊 BRD File:"))
        self.btn_brd = QPushButton("Select File...")
        self.btn_brd.setObjectName("fileUpload")
        self.btn_brd.clicked.connect(self.load_brd)
        self.btn_brd.setCursor(Qt.PointingHandCursor)
        self.btn_brd.setMaximumWidth(100)
        self.btn_brd.setStyleSheet("padding: 6px 12px; font-size: 11px; background-color: #3b82f6; color: white; border-radius: 4px;")
        brd_row1.addStretch()
        brd_row1.addWidget(self.btn_brd)
        brd_inner.addLayout(brd_row1)
        
        self.lbl_brd = QLabel("No file loaded")
        self.lbl_brd.setObjectName("filenameEmpty")
        self.lbl_brd.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_brd.setWordWrap(True)
        brd_inner.addWidget(self.lbl_brd)
        
        # BRD sheet selector
        brd_sheet_row = QHBoxLayout()
        brd_sheet_row.addWidget(QLabel("Sheet:"))
        self.combo_brd_sheet = QComboBox()
        self.combo_brd_sheet.setPlaceholderText("Select...")
        brd_sheet_row.addWidget(self.combo_brd_sheet, 1)
        brd_inner.addLayout(brd_sheet_row)
        
        left_layout.addWidget(self.brd_frame)

        # === STEP 2: Task Configuration (MOVED UP FROM STEP 3) ===
        step2_label = QLabel("STEP 2: CONFIGURATION")
        step2_label.setObjectName("stepLabel")
        step2_label.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 11px; letter-spacing: 1px; margin-top: 8px;")
        left_layout.addWidget(step2_label)
        
        config_frame = QFrame()
        config_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(12, 10, 12, 10)
        config_layout.setSpacing(8)
        
        # Parent Task Name
        config_layout.addWidget(QLabel("Parent Task Name:"))
        self.inp_parent = QLineEdit()
        self.inp_parent.setPlaceholderText("e.g., P0 All Devices or P1 Malbec")
        config_layout.addWidget(self.inp_parent)
        
        # Device
        config_layout.addWidget(QLabel("Target Device:"))
        self.combo_device = QComboBox()
        self.combo_device.addItems(self.config.get_devices())
        config_layout.addWidget(self.combo_device)
        
        # Assignee
        config_layout.addWidget(QLabel("👤 Assignee:"))
        self.combo_assignee = QComboBox()
        self.combo_assignee.setPlaceholderText("Select assignee...")
        self._populate_assignee_dropdown()
        config_layout.addWidget(self.combo_assignee)
        
        # Dashboard Component (OOBE only - hidden by default)
        self.lbl_dashboard_component = QLabel("Dashboard Component (OOBE):")
        self.lbl_dashboard_component.hide()
        config_layout.addWidget(self.lbl_dashboard_component)
        
        self.combo_dashboard_component = QComboBox()
        self.combo_dashboard_component.hide()
        config_layout.addWidget(self.combo_dashboard_component)
        
        # Project name
        config_layout.addWidget(QLabel("Project Name:"))
        self.inp_project = QLineEdit()
        self.inp_project.setPlaceholderText("e.g., J19.3 Mainline")
        config_layout.addWidget(self.inp_project)
        
        # Section
        config_layout.addWidget(QLabel("Section:"))
        self.inp_section = QLineEdit()
        self.inp_section.setPlaceholderText("e.g., Week_05 J19.3")
        config_layout.addWidget(self.inp_section)
        
        left_layout.addWidget(config_frame)

        # === STEP 3: BRD Columns (MOVED FROM STEP 2) ===
        self.step3_label = QLabel("STEP 3: BRD COLUMNS")
        self.step3_label.setObjectName("stepLabel")
        self.step3_label.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 11px; letter-spacing: 1px; margin-top: 8px;")
        left_layout.addWidget(self.step3_label)
        
        self.brd_cols_frame = QFrame()
        brd_cols_frame = self.brd_cols_frame
        brd_cols_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        brd_cols_layout = QVBoxLayout(brd_cols_frame)
        brd_cols_layout.setContentsMargins(10, 10, 10, 10)
        brd_cols_layout.setSpacing(8)
        
        self.btn_viewer = QPushButton("🔍 Open Spreadsheet Viewer")
        self.btn_viewer.clicked.connect(self.open_brd_viewer)
        self.btn_viewer.setCursor(Qt.PointingHandCursor)
        self.btn_viewer.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        brd_cols_layout.addWidget(self.btn_viewer)
        
        # Selected columns display - compact
        cols_row = QHBoxLayout()
        cols_row.setSpacing(8)
        
        perf_box = QFrame()
        perf_box.setStyleSheet("background: #ecfdf5; border: 1px solid #86efac; border-radius: 4px;")
        perf_inner = QVBoxLayout(perf_box)
        perf_inner.setContentsMargins(8, 6, 8, 6)
        perf_inner.addWidget(QLabel("Perf:"))
        self.lbl_perf_col = QLabel("Not selected")
        self.lbl_perf_col.setStyleSheet("color: #059669; font-weight: bold; font-size: 10px;")
        self.lbl_perf_col.setWordWrap(True)
        perf_inner.addWidget(self.lbl_perf_col)
        cols_row.addWidget(perf_box, 1)
        
        prev_box = QFrame()
        prev_box.setStyleSheet("background: #fef3c7; border: 1px solid #fcd34d; border-radius: 4px;")
        prev_inner = QVBoxLayout(prev_box)
        prev_inner.setContentsMargins(8, 6, 8, 6)
        prev_inner.addWidget(QLabel("Previous:"))
        self.lbl_prev_col = QLabel("Not selected")
        self.lbl_prev_col.setStyleSheet("color: #b45309; font-weight: bold; font-size: 10px;")
        self.lbl_prev_col.setWordWrap(True)
        prev_inner.addWidget(self.lbl_prev_col)
        cols_row.addWidget(prev_box, 1)
        
        brd_cols_layout.addLayout(cols_row)
        left_layout.addWidget(self.brd_cols_frame)

        # === MANUAL MODE: Manage Subtasks button (hidden by default) ===
        self.manual_section = QFrame()
        self.manual_section.setStyleSheet("background: #ffffff; border: 1px solid #fcd34d; border-radius: 6px;")
        manual_inner = QVBoxLayout(self.manual_section)
        manual_inner.setContentsMargins(10, 10, 10, 10)
        manual_inner.setSpacing(8)
        
        self.btn_manage_subtasks = QPushButton("📝 Manage Subtasks...")
        self.btn_manage_subtasks.clicked.connect(self._open_manual_subtask_dialog)
        self.btn_manage_subtasks.setCursor(Qt.PointingHandCursor)
        self.btn_manage_subtasks.setStyleSheet("""
            QPushButton {
                background-color: #f59e0b; border: none; border-radius: 6px;
                color: white; font-weight: bold; font-size: 12px; padding: 10px;
            }
            QPushButton:hover { background-color: #d97706; }
        """)
        manual_inner.addWidget(self.btn_manage_subtasks)
        
        self.lbl_manual_count = QLabel("📝 0 manual subtasks")
        self.lbl_manual_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_manual_count.setAlignment(Qt.AlignCenter)
        manual_inner.addWidget(self.lbl_manual_count)
        
        self.manual_section.hide()  # Hidden by default (Template mode)
        left_layout.addWidget(self.manual_section)

        # === ADD TO QUEUE BUTTON ===
        self.btn_add = QPushButton("➕ Add to Queue")
        self.btn_add.setObjectName("success")
        self.btn_add.clicked.connect(self.add_to_queue)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setMinimumHeight(40)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        left_layout.addWidget(self.btn_add)

        left_layout.addStretch()


        # --- RIGHT PANEL (Queue & Preview) - LIGHT THEME ---
        right = QWidget()
        right.setStyleSheet("background-color: #ffffff;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 16, 20, 16)
        right_layout.setSpacing(12)
        splitter.addWidget(right)
        
        # Queue header
        queue_header = QHBoxLayout()
        self.lbl_queue_title = QLabel("📋 Configuration Queue")
        self.lbl_queue_title.setStyleSheet("color: #1e293b; font-size: 16px; font-weight: bold;")
        queue_header.addWidget(self.lbl_queue_title)
        queue_header.addStretch()
        
        self.lbl_queue_count = QLabel("0 configurations, 0 tasks")
        self.lbl_queue_count.setStyleSheet("color: #64748b; font-size: 12px;")
        queue_header.addWidget(self.lbl_queue_count)
        right_layout.addLayout(queue_header)
        
        # Queue list
        self.queue_list = QListWidget()
        self.queue_list.setMinimumHeight(120)
        self.queue_list.setMaximumHeight(160)
        self.queue_list.setStyleSheet("""
            QListWidget {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                margin: 3px;
                padding: 10px;
                border-left: 3px solid #3b82f6;
                color: #1e293b;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                border-color: #3b82f6;
            }
        """)
        right_layout.addWidget(self.queue_list)
        
        # Queue action buttons
        queue_actions = QHBoxLayout()
        queue_actions.setSpacing(10)
        
        self.btn_clear = QPushButton("🗑️ Clear Queue")
        self.btn_clear.setObjectName("danger")
        self.btn_clear.clicked.connect(self.clear_queue)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fecaca;
                border-radius: 6px;
                color: #dc2626;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #fecaca;
            }
        """)
        queue_actions.addWidget(self.btn_clear)
        
        queue_actions.addStretch()
        
        self.btn_preview = QPushButton("👁️ Preview Tasks")
        self.btn_preview.clicked.connect(self.preview_tasks)
        self.btn_preview.setCursor(Qt.PointingHandCursor)
        self.btn_preview.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        queue_actions.addWidget(self.btn_preview)
        
        self.btn_export = QPushButton("💾 Export CSV")
        self.btn_export.setObjectName("success")
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        queue_actions.addWidget(self.btn_export)
        
        right_layout.addLayout(queue_actions)
        
        # Preview section
        preview_header = QLabel("📊 Task Preview")
        preview_header.setStyleSheet("color: #1e293b; font-size: 14px; font-weight: bold; margin-top: 10px;")
        right_layout.addWidget(preview_header)
        
        self.table = QTableView()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableView {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #e2e8f0;
                color: #1e293b;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #475569;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: bold;
                font-size: 11px;
                text-transform: uppercase;
            }
        """)
        right_layout.addWidget(self.table, 1)

        # Splitter sizes
        splitter.setSizes([320, 1080])
        
        # Add Tab 1
        self.tab_widget.addTab(task_creator_tab, "⚡ Task Creator")
        
        # === TAB 2: REPORT GENERATOR ===
        self.report_tab = ReportGeneratorTab(parent_window=self)
        self.tab_widget.addTab(self.report_tab, "📊 Report Generator")

        # === TAB 3: SETTINGS ===
        from ui.settings_dialog import SettingsTab
        self.settings_tab = SettingsTab(config_manager=self.config, parent_window=self)
        self.tab_widget.addTab(self.settings_tab, "⚙️ Settings")
        
        # Connect signals after all UI elements are created
        self.combo_template_sheet.currentIndexChanged.connect(self._on_template_sheet_changed)
        self.combo_brd_sheet.currentIndexChanged.connect(self._on_brd_sheet_changed)

    def _separator(self):
        """Create a visual separator line."""
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #334155; max-height: 1px;")
        return sep

    # ====================
    # FILE LOADERS
    # ====================
    
    def _on_brd_sheet_changed(self):
        """Handle BRD sheet selection changes. Reset column selections when sheet changes."""
        self.selectedPerfCol = {"name": "", "columnIndex": -1}
        self.selectedPrevCol = {"name": "", "columnIndex": -1}
        self.lbl_perf_col.setText("Not selected")
        self.lbl_prev_col.setText("Not selected")
        self.lbl_perf_col.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 10px;")
        self.lbl_prev_col.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 10px;")
        
        sheet_name = self._get_sheet_name(self.combo_brd_sheet)
        if sheet_name:
            logger.info(f"BRD sheet changed to: {sheet_name}")
            self.lbl_status.setText(f"BRD sheet: {sheet_name} — Select columns via Spreadsheet Viewer")

    def _on_template_sheet_changed(self):
        """Handle template sheet selection changes. Show OOBE component dropdown if OOBE sheet."""
        sheet_name = self._get_sheet_name(self.combo_template_sheet)
        
        if not sheet_name or sheet_name not in self.templateSheets:
            # Hide OOBE component selector
            self.lbl_dashboard_component.hide()
            self.combo_dashboard_component.hide()
            return
        
        template_df = self.templateSheets[sheet_name]
        
        # Check if OOBE sheet
        if self._is_oobe_sheet(template_df, sheet_name):
            # Show OOBE component selector
            self.lbl_dashboard_component.show()
            self.combo_dashboard_component.show()
            
            # Populate with unique component values from template
            self.combo_dashboard_component.clear()
            if 'New_Dashboard_Component' in template_df.columns:
                components = template_df['New_Dashboard_Component'].dropna().unique()
                # Filter out empty strings and 'nan'
                components = [str(c).strip() for c in components 
                             if c and str(c).lower() not in ['nan', 'none', '']]
                components = sorted(set(components))  # Remove duplicates and sort
                
                for comp in components:
                    self.combo_dashboard_component.addItem(comp)
        else:
            # Hide OOBE component selector for non-OOBE sheets
            self.lbl_dashboard_component.hide()
            self.combo_dashboard_component.hide()

    def load_template(self):
        """Load template file (CSV or Excel)."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Template File", "", "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )
        if not fname:
            return
            
        try:
            self.templateFilePath = fname
            
            if fname.lower().endswith('.csv'):
                df = pd.read_csv(fname)
                sheet_name = os.path.splitext(os.path.basename(fname))[0]
                self.templateSheets = {sheet_name: df}
            else:
                self.templateSheets = DataLoader.load_all_template_sheets(fname)
            
            self.lbl_template.setText(f"✓ {os.path.basename(fname)}")
            self.lbl_template.setStyleSheet("color: #10b981; font-size: 12px;")
            
            # Populate sheet selector
            self.combo_template_sheet.clear()
            for name, df in self.templateSheets.items():
                self.combo_template_sheet.addItem(f"{name} ({len(df)} rows)", name)
                
            self.lbl_status.setText(f"Template loaded: {len(self.templateSheets)} sheet(s)")
            logger.info(f"Template loaded: {os.path.basename(fname)} with {len(self.templateSheets)} sheets")
            
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load template:\n{str(e)}")
            self.lbl_template.setText("❌ Error loading file")
            self.lbl_template.setStyleSheet("color: #ef4444;")

    def load_brd(self):
        """Load BRD file as raw data."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select BRD File", "", "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not fname:
            return
            
        try:
            self.brdFilePath = fname
            self.brdSheets = DataLoader.load_all_sheets_as_raw(fname)
            
            self.lbl_brd.setText(f"✓ {os.path.basename(fname)}")
            self.lbl_brd.setStyleSheet("color: #10b981; font-size: 12px;")
            
            # Populate BRD sheet selector
            self.combo_brd_sheet.clear()
            for name, data in self.brdSheets.items():
                row_count = len(data) - 1 if data else 0
                self.combo_brd_sheet.addItem(f"{name} ({row_count} rows)", name)
                
            # Reset column selections (handled by _on_brd_sheet_changed signal)
            self.selectedPerfCol = {"name": "", "columnIndex": -1}
            self.selectedPrevCol = {"name": "", "columnIndex": -1}
            self.lbl_perf_col.setText("Not selected")
            self.lbl_prev_col.setText("Not selected")
            
            self.lbl_status.setText(f"BRD loaded: {len(self.brdSheets)} sheet(s) - Now select columns")
            logger.info(f"BRD loaded: {os.path.basename(fname)} with {len(self.brdSheets)} sheets")
            
        except Exception as e:
            logger.error(f"Failed to load BRD: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load BRD:\n{str(e)}")
            self.lbl_brd.setText("❌ Error loading file")
            self.lbl_brd.setStyleSheet("color: #ef4444;")

    def _get_sheet_name(self, combo: QComboBox) -> str:
        """Extract actual sheet name from combo box."""
        return combo.currentData() or ""

    # ====================
    # BRD VIEWER
    # ====================

    def open_brd_viewer(self):
        """Open the BRD spreadsheet viewer for column selection."""
        brd_sheet_name = self._get_sheet_name(self.combo_brd_sheet)
        
        if not self.brdSheets or not brd_sheet_name:
            QMessageBox.warning(self, "No BRD Data", 
                "Please load a BRD file and select a sheet first.")
            return
            
        brd_data = self.brdSheets.get(brd_sheet_name, [])
        if not brd_data:
            QMessageBox.warning(self, "Empty Sheet", "Selected sheet has no data.")
            return
        
        # Get current device for auto-search in BRD viewer
        device_name = self.combo_device.currentText()
            
        # Open dialog with device name for auto-search
        dialog = BrdViewerDialog(brd_data, self, initial_search=device_name)
        
        # Pre-fill current selections
        dialog.selected_perf_col = {
            "name": self.selectedPerfCol.get("name", ""),
            "index": self.selectedPerfCol.get("columnIndex", -1)
        }
        dialog.selected_prev_col = {
            "name": self.selectedPrevCol.get("name", ""),
            "index": self.selectedPrevCol.get("columnIndex", -1)
        }
        
        if dialog.exec_():
            selection = dialog.get_selection()
            
            self.selectedPerfCol = {
                "name": selection['perf'].get('name', ''),
                "columnIndex": selection['perf'].get('index', -1)
            }
            self.selectedPrevCol = {
                "name": selection['prev'].get('name', ''),
                "columnIndex": selection['prev'].get('index', -1)
            }
            
            # Update UI
            perf_name = self.selectedPerfCol['name']
            prev_name = self.selectedPrevCol['name']
            
            self.lbl_perf_col.setText(perf_name[:35] + "..." if len(perf_name) > 35 else perf_name or "Not selected")
            self.lbl_prev_col.setText(prev_name[:35] + "..." if len(prev_name) > 35 else prev_name or "Not selected")
            
            self.lbl_status.setText(f"Columns selected: Perf='{perf_name[:20]}...', Prev='{prev_name[:20]}...'")

    # ====================
    # QUEUE MANAGEMENT
    # ====================

    def _is_manual_mode(self) -> bool:
        """Check if currently in manual (ad-hoc) mode."""
        return self.btn_manual_mode.isChecked()

    def add_to_queue(self):
        """Add current configuration to the queue. Supports both template and manual modes."""
        is_manual = self._is_manual_mode()
        
        # Common validation
        parent_task = self.inp_parent.text().strip()
        if not parent_task:
            QMessageBox.warning(self, "Missing Parent Task", 
                "Please enter a Parent Task Name.\n\nExample: P1 (8) - WiFi Stability")
            self.inp_parent.setFocus()
            return
        
        device = self.combo_device.currentText()
        assignee_name = self.combo_assignee.currentText()
        assignee_email = self.config.get_assignee_email(assignee_name) if assignee_name else ''
        manual_count = len(self.manualSubtasks)
        
        if is_manual:
            # === MANUAL MODE: no template required ===
            if manual_count == 0:
                QMessageBox.warning(self, "No Subtasks", 
                    "Please add at least one manual subtask.\n\n"
                    "Click '📝 Manage Subtasks...' to add test cases.")
                return
            
            config = {
                'parentTask': parent_task,
                'device': device,
                'templateSheet': '(manual)',
                'brdSheet': '',
                'perfColumnInfo': {"name": "", "columnIndex": -1},
                'prevColumnInfo': {"name": "", "columnIndex": -1},
                'project': self.inp_project.text(),
                'section': self.inp_section.text(),
                'estimatedTasks': 0,
                'oobeComponent': '',
                'assigneeName': assignee_name,
                'assigneeEmail': assignee_email,
                'manualSubtasks': list(self.manualSubtasks),
                'isManual': True
            }
            
            self.configQueue.append(config)
            self._render_queue()
            self._save_queue_to_file()
            
            self.inp_parent.clear()
            self.inp_parent.setFocus()
            
            self.lbl_status.setText(f"Added (manual): {parent_task} ({manual_count} subtasks)")
            logger.info(f"Added manual to queue: '{parent_task}' - {device} ({manual_count} subtasks)")
        else:
            # === TEMPLATE MODE: existing behavior ===
            if not self.templateSheets:
                QMessageBox.warning(self, "Missing Template", "Please load a template file first.")
                return
            
            sheet_name = self._get_sheet_name(self.combo_template_sheet)
            if not sheet_name or sheet_name not in self.templateSheets:
                QMessageBox.warning(self, "Missing Sheet", "Please select a template sheet.")
                return
            
            # Calculate ACTUAL task count (only applicable tasks)
            template_df = self.templateSheets[sheet_name]
            brd_sheet = self._get_sheet_name(self.combo_brd_sheet)
            brd_data = self.brdSheets.get(brd_sheet, []) if brd_sheet else []
            
            task_count = 0
            for _, row in template_df.iterrows():
                scenario = ''
                for col in ['Performance Scenario', 'Scenario Name', 'Name']:
                    if col in row.index:
                        val = row.get(col)
                        if val and str(val).lower() not in ['nan', 'none', '']:
                            scenario = str(val).strip()
                            break
                
                if not scenario:
                    continue
                if not self._is_device_applicable_in_template(row, device):
                    continue
                if brd_data and len(brd_data) > 1:
                    brd_match = self._match_brd_for_task(
                        scenario, device, row, template_df, sheet_name,
                        brd_data,
                        self.selectedPerfCol.get('columnIndex', -1),
                        self.selectedPrevCol.get('columnIndex', -1)
                    )
                    if not brd_match.get('applicable', True):
                        continue
                task_count += 1
            
            oobe_component = ''
            if self._is_oobe_sheet(template_df, sheet_name):
                oobe_component = self.combo_dashboard_component.currentText()
            
            config = {
                'parentTask': parent_task,
                'device': device,
                'templateSheet': sheet_name,
                'brdSheet': brd_sheet,
                'perfColumnInfo': self.selectedPerfCol.copy(),
                'prevColumnInfo': self.selectedPrevCol.copy(),
                'project': self.inp_project.text(),
                'section': self.inp_section.text(),
                'estimatedTasks': task_count,
                'oobeComponent': oobe_component,
                'assigneeName': assignee_name,
                'assigneeEmail': assignee_email,
                'manualSubtasks': list(self.manualSubtasks),
                'isManual': False
            }
            
            self.configQueue.append(config)
            self._render_queue()
            self._save_queue_to_file()
            
            self.inp_parent.clear()
            self.inp_parent.setFocus()
            
            manual_info = f" + {manual_count} manual" if manual_count > 0 else ""
            self.lbl_status.setText(f"Added: {parent_task} ({task_count} tasks{manual_info})")
            logger.info(f"Added to queue: '{parent_task}' - {device} - {sheet_name} ({task_count} tasks{manual_info})")

    def _render_queue(self):
        """Render the queue as list items with right-click context menu."""
        self.queue_list.clear()
        
        total_tasks = 0
        for idx, config in enumerate(self.configQueue):
            total_tasks += config.get('estimatedTasks', 0)
            
            manual_sub_count = len(config.get('manualSubtasks', []))
            assignee_display = f"  •  👤 {config.get('assigneeName', '')}" if config.get('assigneeName') else ""
            manual_display = f" + {manual_sub_count} manual" if manual_sub_count > 0 else ""
            text = f"📌 {config['parentTask']}  •  📱 {config['device']}{assignee_display}  •  📄 {config['templateSheet']}  •  ~{config.get('estimatedTasks', 0)} tasks{manual_display}"
            
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, idx)
            self.queue_list.addItem(item)
        
        # Enable context menu for individual item removal
        self.queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        try:
            self.queue_list.customContextMenuRequested.disconnect()
        except TypeError:
            pass
        self.queue_list.customContextMenuRequested.connect(self._show_queue_context_menu)
            
        self.lbl_queue_count.setText(f"{len(self.configQueue)} configuration(s), ~{total_tasks} tasks")

    def _show_queue_context_menu(self, position):
        """Show right-click context menu on queue items for removal."""
        item = self.queue_list.itemAt(position)
        if not item:
            return
        
        idx = item.data(Qt.UserRole)
        menu = QMenu(self)
        
        remove_action = menu.addAction("🗑️ Remove this configuration")
        remove_action.setData(idx)
        
        action = menu.exec_(self.queue_list.mapToGlobal(position))
        if action == remove_action:
            self._remove_queue_item(idx)

    def _remove_queue_item(self, index: int):
        """Remove a single item from the queue by index."""
        if 0 <= index < len(self.configQueue):
            removed = self.configQueue.pop(index)
            logger.info(f"Removed from queue: {removed.get('parentTask', 'unknown')}")
            self._render_queue()
            self._save_queue_to_file()
            self.lbl_status.setText(f"Removed: {removed.get('parentTask', '')}")

    def clear_queue(self):
        """Clear all configurations from queue."""
        if self.configQueue:
            reply = QMessageBox.question(self, "Clear Queue?", 
                f"Remove all {len(self.configQueue)} configurations from queue?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
                
        self.configQueue = []
        self.queue_list.clear()
        self.table.setModel(None)
        self.lbl_queue_count.setText("0 configurations, 0 tasks")
        self.lbl_status.setText("Queue cleared")
        self._save_queue_to_file()

    # ====================
    # PREVIEW & EXPORT
    # ====================

    def _is_new_feature_brd_sheet(self, brd_data: list) -> bool:
        """
        Check if the BRD sheet is a 'New Feature' sheet that groups multiple feature
        categories (Color Stroke, HWR Search, Keyboard Canvas, Q&A) in one sheet.
        
        Detected by presence of a 'New Feature' column in BRD data headers.
        """
        if not brd_data or len(brd_data) < 1:
            return False
        return self.brdMatcher.find_new_feature_column(brd_data) != -1

    def _get_feature_category_from_row(self, row) -> str:
        """
        Get the feature category from a Template row.
        Uses the 'Priority' column value as the feature category for New Feature matching.
        """
        priority = row.get('Priority', '')
        if str(priority).lower() in ['nan', 'none', '']:
            return ''
        return str(priority).strip()

    def _match_brd_for_task(self, scenario: str, device: str, template_row, 
                            template_df, template_sheet: str, brd_data: list,
                            perf_idx: int, prev_idx: int, config: dict = None) -> dict:
        """
        Unified BRD matching logic that selects the appropriate matching strategy based on the BRD sheet type:
        1. OOBE sheet: utilizes multi-criteria matching
        2. New Feature BRD sheet: leverages scenario mapping
        3. Standard sheet: applies basic matching

        Returns:
            Dict with {applicable, perf_value, prev_value}
        """
        if not brd_data or len(brd_data) < 2:
            logger.info(f"[MATCH] No BRD data for scenario='{scenario}' (brd_data len={len(brd_data) if brd_data else 0})")
            return {'applicable': True, 'perf_value': '-', 'prev_value': '-'}
        
        logger.info(f"[MATCH] scenario='{scenario}', device='{device}', perf_idx={perf_idx}, prev_idx={prev_idx}, "
                    f"brd_rows={len(brd_data)}, template_sheet='{template_sheet}'")
        
        # Strategy 1: OOBE matching
        if self._is_oobe_sheet(template_df, template_sheet):
            component = ''
            if config:
                component = config.get('oobeComponent', '')
            elif self.combo_dashboard_component.isVisible():
                component = self.combo_dashboard_component.currentText()
            
            return self.brdMatcher.get_brd_data_for_oobe_task(
                scenario, device, component, '',
                brd_data, perf_idx, prev_idx
            )
        
        # Strategy 2: New Feature matching (BRD has 'New Feature' column)
        if self._is_new_feature_brd_sheet(brd_data):
            feature_category = self._get_feature_category_from_row(template_row)
            if feature_category:
                logger.debug(f"Using New Feature matching: scenario='{scenario}', feature='{feature_category}'")
                return self.brdMatcher.get_brd_data_for_new_feature_task(
                    scenario, device, feature_category,
                    brd_data, perf_idx, prev_idx
                )
        
        # Strategy 3: Standard matching
        return self.brdMatcher.get_brd_data_for_task(
            scenario, device, brd_data, perf_idx, prev_idx
        )

    def _is_oobe_sheet(self, template_df, sheet_name: str) -> bool:
        """
        Check if this is an OOBE sheet requiring multi-criteria matching.
        
        OOBE sheets are identified by:
        1. Sheet name contains 'OOBE' (case-insensitive)
        2. Template has 'New_Dashboard_Component' column
        3. Template has 'Sub_Priority' column
        """
        # Check sheet name
        if 'oobe' not in sheet_name.lower():
            return False
        
        # Check for required columns
        has_component = 'New_Dashboard_Component' in template_df.columns
        has_subpriority = 'Sub_Priority' in template_df.columns
        
        return has_component and has_subpriority

    def _is_device_applicable_in_template(self, row, device: str, debug: bool = False) -> bool:
        """
        Check if the task is applicable for the selected device
        based on Template's 'Applicable Devices' column.
        
        The Template has a column like 'Applicable Devices' with values like:
        'Malbec,Cava,Barolo,Pisco,Sangria,Calvados,Seabreeze'
        """
        # Find the Applicable Devices column (try multiple possible names)
        applicable_value = None
        found_col = None
        for col_name in ['Applicable Devices', 'Applicable', 'Devices', 'Device']:
            if col_name in row.index:
                applicable_value = row.get(col_name)
                found_col = col_name
                break
        
        if debug:
            print(f"[DEBUG Template] Columns in row: {list(row.index)[:5]}...")
            print(f"[DEBUG Template] Found column: {found_col}, Value: '{applicable_value}'")
        
        if applicable_value is None or str(applicable_value).lower() in ['nan', 'none', '']:
            # No applicable devices column or empty = applicable to all
            if debug:
                print(f"[DEBUG Template] No value found - APPLICABLE TO ALL")
            return True
            
        # Parse the comma-separated list
        applicable_str = str(applicable_value).strip()
        applicable_list = [d.strip().lower() for d in applicable_str.split(',')]
        
        # Check if selected device is in the list
        device_lower = device.lower().strip()
        
        # 'all' in the list means applicable to all devices
        if 'all' in applicable_list:
            if debug:
                print(f"[DEBUG Template] 'all' in list - APPLICABLE")
            return True
        
        is_applicable = device_lower in applicable_list
        if debug:
            print(f"[DEBUG Template] Device '{device_lower}' in {applicable_list[:3]}...? = {is_applicable}")
            
        return is_applicable

    def preview_tasks(self):
        """Generate and preview all tasks from queue."""
        if not self.configQueue:
            QMessageBox.warning(self, "Empty Queue", 
                "Add configurations to the queue first.\n\n"
                "1. Fill in Parent Task Name\n"
                "2. Select Device\n"
                "3. Click 'Add Configuration to Queue'")
            return
            
        all_tasks = []
        skipped_template = 0  # Filtered by Template's Applicable Devices
        skipped_brd = 0       # Filtered by BRD matching
        
        for config in self.configQueue:
            device = config['device']
            is_manual_entry = config.get('isManual', False)
            template_sheet = config['templateSheet']
            
            # Process template tasks (only for non-manual entries)
            if not is_manual_entry and template_sheet in self.templateSheets:
                template_df = self.templateSheets[template_sheet]
                
                brd_sheet = config.get('brdSheet')
                brd_data = self.brdSheets.get(brd_sheet, []) if brd_sheet else []
                perf_idx = config['perfColumnInfo'].get('columnIndex', -1)
                prev_idx = config['prevColumnInfo'].get('columnIndex', -1)
                
                for _, row in template_df.iterrows():
                    scenario = ''
                    for col in ['Performance Scenario', 'Scenario Name', 'Name']:
                        if col in row.index:
                            val = row.get(col)
                            if val and str(val).lower() not in ['nan', 'none', '']:
                                scenario = str(val).strip()
                                break
                    
                    if not scenario:
                        continue
                    
                    if not self._is_device_applicable_in_template(row, device):
                        skipped_template += 1
                        continue
                        
                    brd_match = {'perf_value': '-', 'prev_value': '-'}
                    if brd_data and len(brd_data) > 1:
                        brd_match = self._match_brd_for_task(
                            scenario, device, row, template_df, template_sheet,
                            brd_data, perf_idx, prev_idx, config=config
                        )
                        
                    priority = row.get('Priority', '')
                    if str(priority).lower() in ['nan', 'none', '']:
                        priority = '-'
                        
                    est_time = row.get('Estimated Time') or row.get('Time', '')
                    
                    task = {
                        'Parent Task': config['parentTask'],
                        'Scenario': scenario,
                        'Device': device,
                        'Priority': str(priority),
                        'Est. Time': self._format_time(est_time),
                        'Perf_BRD': brd_match['perf_value'],
                        'Previous Value': brd_match['prev_value']
                    }
                    all_tasks.append(task)
            
            # Add manual subtasks for this config
            for manual in config.get('manualSubtasks', []):
                task = {
                    'Parent Task': config['parentTask'],
                    'Scenario': f"🔧 {manual['name']}",
                    'Device': device,
                    'Priority': manual.get('priority', ''),
                    'Est. Time': manual.get('est_time', ''),
                    'Perf_BRD': '',
                    'Previous Value': ''
                }
                all_tasks.append(task)
        
        if not all_tasks:
            msg = "No applicable tasks found."
            if skipped_template > 0:
                msg += f"\n\n{skipped_template} tasks filtered - device '{self.configQueue[0]['device'] if self.configQueue else 'unknown'}' not in Template's 'Applicable Devices' column."
            QMessageBox.information(self, "No Tasks", msg)
            return
            
        # Display in table
        columns = ['Parent Task', 'Scenario', 'Device', 'Priority', 'Est. Time', 'Perf_BRD', 'Previous Value']
        model = TaskTableModel(all_tasks, columns)
        self.table.setModel(model)
        self.table.resizeColumnsToContents()
        
        status = f"Preview: {len(all_tasks)} tasks"
        if skipped_template > 0:
            status += f" ({skipped_template} filtered by device)"
        self.lbl_status.setText(status)

    def _format_time(self, value) -> str:
        """Format time value for Asana (H:MM format). 
        
        Handles:
        - Already formatted values (e.g., "1:30", "30m", "2h")
        - Simple integers >= 1 treated as minutes (e.g., 90 -> "1:30")
        - Excel decimal format (fraction of 24 hours, e.g., 0.0625 -> "1:30")
        """
        if not value or str(value).lower() in ['nan', 'none', '']:
            return '-'
        val_str = str(value).strip()
        
        # If already formatted (has :, s, m, h), return as-is
        if any(c in val_str for c in [':', 's', 'm', 'h']):
            return val_str
        
        try:
            num = float(val_str)
            
            if num < 0:
                return '-'
            
            # Distinguish between minutes (>=1) and Excel decimal format (<1)
            if num >= 1:
                # Treat as minutes (e.g., 90 -> 1:30)
                hours = int(num // 60)
                minutes = int(num % 60)
                return f"{hours}:{minutes:02d}"
            else:
                # Excel decimal format: fraction of 24 hours (e.g., 0.0625 = 1.5 hours)
                total_minutes = int(num * 24 * 60)
                hours = total_minutes // 60
                minutes = total_minutes % 60
                return f"{hours}:{minutes:02d}"
        except (ValueError, TypeError):
            logger.debug(f"Could not parse time value: '{value}'")
            return val_str

    def export_csv(self):
        """Export all tasks to CSV in Asana format."""
        if not self.configQueue:
            QMessageBox.warning(self, "Empty Queue", "No configurations to export.")
            return
            
        fname, _ = QFileDialog.getSaveFileName(
            self, "Save CSV File", "asana_export.csv", "CSV Files (*.csv)"
        )
        if not fname:
            return
            
        try:
            rows = self._generate_export_rows()
            
            if not rows:
                QMessageBox.warning(self, "No Tasks", "No applicable tasks to export.")
                return
                
            df = pd.DataFrame(rows)
            df.to_csv(fname, index=False)
            
            QMessageBox.information(self, "Export Complete", 
                f"✓ Exported {len(rows)} rows to:\n{fname}")
            self.lbl_status.setText(f"Exported {len(rows)} rows")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    def _generate_export_rows(self) -> list:
        """Generate all rows for CSV export in Asana format."""
        # Asana CSV column headers — from config
        HEADERS = self.config.get_export_headers()
        
        all_rows = []
        
        for config in self.configQueue:
            is_manual_entry = config.get('isManual', False)
            template_sheet = config['templateSheet']
            device = config['device']
            section = config['section']
            project = config['project']
            parent_task = config['parentTask']
            
            # Add parent task row
            parent_row = {h: '' for h in HEADERS}
            parent_row['Name'] = parent_task
            parent_row['Section/Column'] = section
            parent_row['Projects'] = project
            all_rows.append(parent_row)
            
            # Add template task rows (only for non-manual entries)
            if not is_manual_entry and template_sheet in self.templateSheets:
                template_df = self.templateSheets[template_sheet]
                brd_sheet = config.get('brdSheet')
                brd_data = self.brdSheets.get(brd_sheet, []) if brd_sheet else []
                perf_idx = config['perfColumnInfo'].get('columnIndex', -1)
                prev_idx = config['prevColumnInfo'].get('columnIndex', -1)
                
                for _, template_row in template_df.iterrows():
                    scenario = ''
                    for col in ['Performance Scenario', 'Scenario Name', 'Name']:
                        if col in template_row.index:
                            val = template_row.get(col)
                            if val and str(val).lower() not in ['nan', 'none', '']:
                                scenario = str(val).strip()
                                break
                    
                    if not scenario:
                        continue
                    
                    if not self._is_device_applicable_in_template(template_row, device):
                        continue
                        
                    brd_match = {'applicable': True, 'perf_value': '-', 'prev_value': '-'}
                    if brd_data and len(brd_data) > 1:
                        brd_match = self._match_brd_for_task(
                            scenario, device, template_row, template_df, template_sheet,
                            brd_data, perf_idx, prev_idx, config=config
                        )
                        if not brd_match.get('applicable', True):
                            continue
                        
                    est_time = template_row.get('Estimated Time') or template_row.get('Time', '')
                    priority = template_row.get('Priority', '')
                    if str(priority).lower() in ['nan', 'none', '']:
                        priority = ''
                    
                    task_row = {h: '' for h in HEADERS}
                    task_row['Name'] = scenario
                    task_row['Parent task'] = parent_task
                    task_row['Devices'] = device
                    task_row['Priority'] = str(priority)
                    task_row['Estimated time'] = self._format_time(est_time)
                    task_row['Perf_BRD'] = brd_match['perf_value']
                    task_row['Previous Value'] = brd_match['prev_value']
                    
                    assignee_email = config.get('assigneeEmail', '')
                    if assignee_email:
                        task_row['Assignee Email'] = assignee_email
                    
                    defaults = self.config.get_default_export_values()
                    for dk, dv in defaults.items():
                        task_row[dk] = dv
                    
                    all_rows.append(task_row)
            
            # Add manual subtasks for this config
            for manual in config.get('manualSubtasks', []):
                task_row = {h: '' for h in HEADERS}
                task_row['Name'] = manual['name']
                task_row['Parent task'] = parent_task
                task_row['Devices'] = device
                task_row['Priority'] = manual.get('priority', '')
                task_row['Estimated time'] = manual.get('est_time', '')
                # No Perf_BRD, no Previous Value for manual subtasks
                
                # Set assignee
                assignee_email = config.get('assigneeEmail', '')
                if assignee_email:
                    task_row['Assignee Email'] = assignee_email
                
                # Add default deviation column values
                defaults = self.config.get_default_export_values()
                for dk, dv in defaults.items():
                    task_row[dk] = dv
                
                all_rows.append(task_row)
                
        return all_rows
    
    # ====================
    # QUEUE PERSISTENCE
    # ====================
    
    def _save_queue_to_file(self):
        """Save queue to JSON file for persistence across app restarts."""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(self.configQueue, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save queue: {e}")
    
    def _load_queue_from_file(self):
        """Load queue from JSON file if it exists."""
        if not os.path.exists(self.queue_file):
            return
            
        try:
            with open(self.queue_file, 'r') as f:
                self.configQueue = json.load(f)
            
            if self.configQueue:
                self._render_queue()
                self.lbl_status.setText(f"Loaded {len(self.configQueue)} saved configuration(s)")
                logger.info(f"Loaded {len(self.configQueue)} saved queue configurations")
        except Exception as e:
            logger.warning(f"Could not load queue: {e}")
            self.configQueue = []
    
    # ====================
    # MODE TOGGLE & MANUAL SUBTASKS
    # ====================
    
    def _set_mode(self, mode: str):
        """Toggle between Template and Manual mode."""
        is_template = (mode == 'template')
        
        # Update toggle buttons
        self.btn_template_mode.setChecked(is_template)
        self.btn_manual_mode.setChecked(not is_template)
        
        # Show/hide template-specific sections
        self.step1_label.setVisible(is_template)
        self.tmpl_frame.setVisible(is_template)
        self.brd_frame.setVisible(is_template)
        self.step3_label.setVisible(is_template)
        self.brd_cols_frame.setVisible(is_template)
        
        # Show/hide manual section
        self.manual_section.setVisible(not is_template)
        
        self.lbl_status.setText(f"Mode: {'Template' if is_template else 'Manual (Ad-Hoc)'}")
    
    def _open_manual_subtask_dialog(self):
        """Open the manual subtask management popup dialog."""
        dialog = ManualSubtaskDialog(subtasks=self.manualSubtasks, parent=self)
        if dialog.exec_():
            self.manualSubtasks = dialog.get_subtasks()
            self._update_manual_count()
            logger.info(f"Manual subtasks updated: {len(self.manualSubtasks)} subtasks")
    
    def _update_manual_count(self):
        """Update the manual subtask count label."""
        count = len(self.manualSubtasks)
        self.lbl_manual_count.setText(f"📝 {count} manual subtask{'s' if count != 1 else ''}")
        if count > 0:
            self.lbl_manual_count.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_manual_count.setStyleSheet("color: #94a3b8; font-size: 11px;")

    def _populate_profile_dropdown(self):
        """Populate the profile selector dropdown."""
        self.combo_profile.blockSignals(True)
        self.combo_profile.clear()
        profiles = self.config.list_profiles()
        active = self.config.get_active_profile()
        for p in profiles:
            self.combo_profile.addItem(p)
        idx = self.combo_profile.findText(active)
        if idx >= 0:
            self.combo_profile.setCurrentIndex(idx)
        self.combo_profile.blockSignals(False)

    def _on_profile_changed(self, profile_name: str):
        """Handle profile switch from the header dropdown."""
        if not profile_name or profile_name == self.config.get_active_profile():
            return
        
        self.config.switch_profile(profile_name)
        self._refresh_after_profile_switch()
        self.lbl_status.setText(f"Switched to profile: {profile_name}")
        logger.info(f"Profile switched to: {profile_name}")

    def _refresh_after_profile_switch(self):
        """Refresh all UI elements after a profile switch."""
        # Refresh device dropdown
        current_device = self.combo_device.currentText()
        self.combo_device.clear()
        self.combo_device.addItems(self.config.get_devices())
        idx = self.combo_device.findText(current_device)
        if idx >= 0:
            self.combo_device.setCurrentIndex(idx)
        
        # Refresh assignee dropdown
        self._populate_assignee_dropdown()
        
        # Refresh settings tab if it exists
        if hasattr(self, 'settings_tab'):
            self.settings_tab._load_from_config()
        
        # Refresh profile dropdown
        self._populate_profile_dropdown()

    def _populate_assignee_dropdown(self):
        """Populate the assignee dropdown from config."""
        self.combo_assignee.clear()
        self.combo_assignee.addItem("")  # Empty option = no assignee
        for assignee in self.config.get_assignees():
            name = assignee.get('name', '')
            email = assignee.get('email', '')
            if name:
                self.combo_assignee.addItem(name)

    def _load_default_template(self):
        """Auto-load default template file if it exists."""
        if not os.path.exists(self.default_template_path):
            self.lbl_status.setText("⚠️ Place Template.xlsx in resources/ folder for auto-load")
            return
            
        try:
            loader = DataLoader()
            
            # Load all template sheets
            sheets = loader.load_all_template_sheets(self.default_template_path)
            
            # Check if sheets is a valid dict with content
            if sheets is not None and isinstance(sheets, dict) and len(sheets) > 0:
                self.templateSheets = sheets
                self.templateFilePath = self.default_template_path
                
                # Update UI
                filename = os.path.basename(self.default_template_path)
                self.lbl_template.setText(f"✓ {filename} (auto-loaded)")
                self.lbl_template.setStyleSheet("color: #10b981; font-size: 11px;")
                
                # Populate sheet dropdown
                self.combo_template_sheet.clear()
                for sheet_name in sheets.keys():
                    self.combo_template_sheet.addItem(f"📄 {sheet_name}", sheet_name)
                
                self.lbl_status.setText(f"✓ Auto-loaded default template: {len(sheets)} sheet(s)")
                logger.info(f"Auto-loaded default template: {len(sheets)} sheets")
            else:
                self.lbl_status.setText("⚠️ Failed to load default template")
                logger.warning("Default template loaded but contains no valid sheets")
        except Exception as e:
            logger.warning(f"Could not auto-load template: {e}")
            self.lbl_status.setText(f"⚠️ Template auto-load error: {str(e)}")
