"""
Report Generator Tab - Import Asana CSV, filter tasks, and write Average values back to BRD.
"""

import os
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFileDialog, QComboBox, QLineEdit, QTableView, QHeaderView,
                             QMessageBox, QFrame, QScrollArea, QSplitter, QAbstractItemView)
from PyQt5.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer, QModelIndex
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from core.csv_importer import CsvImporter
from core.brd_writer import BrdWriter
from core.data_loader import DataLoader
from core.config_manager import ConfigManager
from core.brd_matcher import BrdMatcher

logger = logging.getLogger('AsanaGenerator.ReportGenerator')


class CsvCellDelegate(QStyledItemDelegate):
    """Custom delegate to paint cell backgrounds for colored columns (like BRD Viewer)."""
    
    # Column indices that need special coloring
    COLOR_COLUMNS = {'BRD Status', 'Previous Status', 'Deviation_BRD', 'Deviation_Prev'}
    
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self._model = model
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """Custom paint to force background colors even when selected."""
        if not index.isValid() or index.column() >= len(self._model.DISPLAY_COLUMNS):
            super().paint(painter, option, index)
            return
        
        col_key = self._model.DISPLAY_COLUMNS[index.column()]
        
        if col_key in self.COLOR_COLUMNS and index.row() < len(self._model._data):
            row_data = self._model._data[index.row()]
            val = row_data.get(col_key, '')
            
            bg_color = None
            fg_color = None
            
            # Deviation columns
            if col_key in ('Deviation_BRD', 'Deviation_Prev'):
                color_key = '_brd_color' if col_key == 'Deviation_BRD' else '_prev_color'
                color = row_data.get(color_key, '')
                if color == 'green':
                    bg_color = QColor('#00B050')
                    fg_color = QColor('#FFFFFF')
                elif color == 'yellow':
                    bg_color = QColor('#FFFF00')
                    fg_color = QColor('#000000')
                elif color == 'red':
                    bg_color = QColor('#FF0000')
                    fg_color = QColor('#FFFFFF')
            
            # Status columns
            elif col_key in ('BRD Status', 'Previous Status'):
                val_upper = str(val).upper()
                if val_upper == 'PASS':
                    bg_color = QColor('#00B050')
                    fg_color = QColor('#FFFFFF')
                elif val_upper == 'FAIL':
                    bg_color = QColor('#FF0000')
                    fg_color = QColor('#FFFFFF')
            
            if bg_color:
                # Force paint background
                painter.fillRect(option.rect, bg_color)
                
                # Draw text
                if fg_color:
                    painter.setPen(fg_color)
                text = str(val)[:100] if val else ''
                painter.drawText(option.rect.adjusted(4, 0, -4, 0), 
                               Qt.AlignVCenter | Qt.AlignLeft, text)
                return
        
        # Default painting for non-colored cells
        super().paint(painter, option, index)


class CsvTableModel(QAbstractTableModel):
    """Table model for displaying filtered CSV task data. Columns driven by config."""

    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
        # Load display columns from config
        config = ConfigManager()
        self.DISPLAY_COLUMNS = config.get_display_column_keys(visible_only=True)
        self.COLUMN_LABELS = config.get_display_column_labels(visible_only=True)
        self._columns = self.DISPLAY_COLUMNS

    def set_data(self, data):
        self.beginResetModel()
        self._data = data or []
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row_data = self._data[index.row()]
        col_key = self._columns[index.column()]
        val = row_data.get(col_key, '')
        
        if role == Qt.DisplayRole:
            return str(val)[:100] if val else ''
        
        if role == Qt.BackgroundRole:
            # Highlight Average column with values
            if col_key == 'Average' and val and val not in ['', '-', '0']:
                return QColor('#ecfdf5')  # Light green
            
            # Color-coded deviation columns — solid GREEN/YELLOW/RED fill
            if col_key == 'Deviation_BRD':
                color = row_data.get('_brd_color', '')
                if color == 'green':
                    return QColor('#00B050')  # Solid green (Excel green)
                elif color == 'yellow':
                    return QColor('#FFFF00')  # Solid yellow (Excel yellow)
                elif color == 'red':
                    return QColor('#FF0000')  # Solid red (Excel red)
            
            if col_key == 'Deviation_Prev':
                color = row_data.get('_prev_color', '')
                if color == 'green':
                    return QColor('#00B050')
                elif color == 'yellow':
                    return QColor('#FFFF00')
                elif color == 'red':
                    return QColor('#FF0000')
            
            # BRD Status — solid fill
            if col_key == 'BRD Status':
                val_upper = str(val).upper()
                if val_upper == 'PASS':
                    return QColor('#00B050')  # Solid green
                elif val_upper == 'FAIL':
                    return QColor('#FF0000')  # Solid red
            
            # Previous Status — solid fill
            if col_key == 'Previous Status':
                val_upper = str(val).upper()
                if val_upper == 'PASS':
                    return QColor('#00B050')
                elif val_upper == 'FAIL':
                    return QColor('#FF0000')
        
        if role == Qt.ForegroundRole:
            # White text on solid color backgrounds for readability
            if col_key == 'BRD Status':
                val_upper = str(val).upper()
                if val_upper == 'PASS':
                    return QColor('#FFFFFF')  # White text on green
                elif val_upper == 'FAIL':
                    return QColor('#FFFFFF')  # White text on red
            
            if col_key == 'Previous Status':
                val_upper = str(val).upper()
                if val_upper == 'PASS':
                    return QColor('#FFFFFF')
                elif val_upper == 'FAIL':
                    return QColor('#FFFFFF')
            
            # White text on solid deviation backgrounds
            if col_key in ('Deviation_BRD', 'Deviation_Prev'):
                color_key = '_brd_color' if col_key == 'Deviation_BRD' else '_prev_color'
                color = row_data.get(color_key, '')
                if color == 'green':
                    return QColor('#FFFFFF')  # White on green
                elif color == 'yellow':
                    return QColor('#000000')  # Black on yellow (better contrast)
                elif color == 'red':
                    return QColor('#FFFFFF')  # White on red
        
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < len(self._columns):
                col_key = self._columns[section]
                return self.COLUMN_LABELS.get(col_key, col_key)
        return None


class ReportGeneratorTab(QWidget):
    """
    Report Generator tab - Import Asana CSV, filter, and write back to BRD.
    """
    
    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        
        # State
        self.csv_data = None       # Parsed CSV data from CsvImporter
        self.csv_file_path = None
        self.brd_file_path = None
        self.brd_sheets = {}       # {sheet_name: List[List[Any]]} raw BRD data
        self.selected_target_col = {"name": "", "columnIndex": -1}
        self.filtered_tasks = []
        
        # Audit Reconciliation state
        self.audit_brd_file_path = None
        self.audit_brd_sheets = {}
        self.audit_selected_col = {"name": "", "columnIndex": -1}
        self.audit_comparison_data = []  # List of comparison dicts
        self.original_counts = {'green': 0, 'yellow': 0, 'red': 0, 'na': 0}
        self.audited_counts = {'green': 0, 'yellow': 0, 'red': 0, 'na': 0}
        
        # Debounce timer for search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._apply_filters)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #e2e8f0; }")
        layout.addWidget(splitter)
        
        # === LEFT SIDEBAR ===
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(300)
        left_scroll.setMaximumWidth(320)
        left_widget = QWidget()
        left_widget.setStyleSheet("background-color: #f8fafc;")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_scroll.setWidget(left_widget)
        splitter.addWidget(left_scroll)
        
        # --- STEP 1: Import CSV ---
        step1_label = QLabel("STEP 1: IMPORT CSV")
        step1_label.setStyleSheet("color: #7c3aed; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        left_layout.addWidget(step1_label)
        
        csv_frame = QFrame()
        csv_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;")
        csv_inner = QVBoxLayout(csv_frame)
        csv_inner.setContentsMargins(10, 8, 10, 8)
        csv_inner.setSpacing(6)
        
        csv_row = QHBoxLayout()
        csv_row.addWidget(QLabel("📥 Asana CSV:"))
        self.btn_import_csv = QPushButton("Import...")
        self.btn_import_csv.clicked.connect(self.import_csv)
        self.btn_import_csv.setCursor(Qt.PointingHandCursor)
        self.btn_import_csv.setMaximumWidth(100)
        self.btn_import_csv.setStyleSheet("padding: 6px 12px; font-size: 11px; background-color: #7c3aed; color: white; border-radius: 4px;")
        csv_row.addStretch()
        csv_row.addWidget(self.btn_import_csv)
        csv_inner.addLayout(csv_row)
        
        self.lbl_csv = QLabel("No file loaded")
        self.lbl_csv.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_csv.setWordWrap(True)
        csv_inner.addWidget(self.lbl_csv)
        
        self.lbl_csv_summary = QLabel("")
        self.lbl_csv_summary.setStyleSheet("color: #64748b; font-size: 10px;")
        self.lbl_csv_summary.setWordWrap(True)
        csv_inner.addWidget(self.lbl_csv_summary)
        
        left_layout.addWidget(csv_frame)
        
        # --- STEP 2: Filters ---
        step2_label = QLabel("STEP 2: FILTER DATA")
        step2_label.setStyleSheet("color: #7c3aed; font-weight: bold; font-size: 11px; letter-spacing: 1px; margin-top: 8px;")
        left_layout.addWidget(step2_label)
        
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        filter_layout = QVBoxLayout(filter_frame)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(8)
        
        # Parent Task filter
        filter_layout.addWidget(QLabel("Parent Task:"))
        self.combo_parent = QComboBox()
        self.combo_parent.addItem("All")
        self.combo_parent.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.combo_parent)
        
        # Section filter
        filter_layout.addWidget(QLabel("Section:"))
        self.combo_section = QComboBox()
        self.combo_section.addItem("All")
        self.combo_section.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.combo_section)
        
        # Device filter
        filter_layout.addWidget(QLabel("Device:"))
        self.combo_device = QComboBox()
        self.combo_device.addItem("All")
        self.combo_device.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.combo_device)
        
        # Search
        filter_layout.addWidget(QLabel("🔍 Search Scenario:"))
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("Type to search...")
        self.inp_search.textChanged.connect(lambda: self.search_timer.start(300))
        filter_layout.addWidget(self.inp_search)
        
        left_layout.addWidget(filter_frame)
        
        # --- STEP 3: BRD Target ---
        step3_label = QLabel("STEP 3: BRD TARGET")
        step3_label.setStyleSheet("color: #7c3aed; font-weight: bold; font-size: 11px; letter-spacing: 1px; margin-top: 8px;")
        left_layout.addWidget(step3_label)
        
        brd_frame = QFrame()
        brd_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        brd_layout = QVBoxLayout(brd_frame)
        brd_layout.setContentsMargins(10, 10, 10, 10)
        brd_layout.setSpacing(8)
        
        # BRD File
        brd_file_row = QHBoxLayout()
        brd_file_row.addWidget(QLabel("📊 BRD File:"))
        self.btn_brd = QPushButton("Select...")
        self.btn_brd.clicked.connect(self.load_brd)
        self.btn_brd.setCursor(Qt.PointingHandCursor)
        self.btn_brd.setMaximumWidth(80)
        self.btn_brd.setStyleSheet("padding: 4px 10px; font-size: 10px; background-color: #7c3aed; color: white; border-radius: 4px;")
        brd_file_row.addStretch()
        brd_file_row.addWidget(self.btn_brd)
        brd_layout.addLayout(brd_file_row)
        
        self.lbl_brd = QLabel("No file loaded")
        self.lbl_brd.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self.lbl_brd.setWordWrap(True)
        brd_layout.addWidget(self.lbl_brd)
        
        # BRD Sheet
        brd_layout.addWidget(QLabel("Sheet:"))
        self.combo_brd_sheet = QComboBox()
        self.combo_brd_sheet.setPlaceholderText("Select...")
        brd_layout.addWidget(self.combo_brd_sheet)
        
        # Target column selection via Spreadsheet Viewer
        self.btn_select_target = QPushButton("🎯 Select Target Column")
        self.btn_select_target.clicked.connect(self.select_target_column)
        self.btn_select_target.setCursor(Qt.PointingHandCursor)
        self.btn_select_target.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                border: none; border-radius: 6px;
                color: white; font-weight: bold; font-size: 11px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #6d28d9; }
        """)
        brd_layout.addWidget(self.btn_select_target)
        
        # Target column display
        target_box = QFrame()
        target_box.setStyleSheet("background: #f5f3ff; border: 1px solid #c4b5fd; border-radius: 4px;")
        target_inner = QVBoxLayout(target_box)
        target_inner.setContentsMargins(8, 6, 8, 6)
        target_inner.addWidget(QLabel("Target Column:"))
        self.lbl_target_col = QLabel("Not selected")
        self.lbl_target_col.setStyleSheet("color: #7c3aed; font-weight: bold; font-size: 10px;")
        self.lbl_target_col.setWordWrap(True)
        target_inner.addWidget(self.lbl_target_col)
        brd_layout.addWidget(target_box)
        
        left_layout.addWidget(brd_frame)
        
        # --- ACTION BUTTONS ---
        self.btn_preview_write = QPushButton("👁️ Preview Write")
        self.btn_preview_write.clicked.connect(self.preview_write)
        self.btn_preview_write.setCursor(Qt.PointingHandCursor)
        self.btn_preview_write.setMinimumHeight(36)
        self.btn_preview_write.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; border: none; border-radius: 6px;
                color: white; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        left_layout.addWidget(self.btn_preview_write)
        
        self.btn_write_brd = QPushButton("📝 Write to BRD")
        self.btn_write_brd.clicked.connect(self.write_to_brd)
        self.btn_write_brd.setCursor(Qt.PointingHandCursor)
        self.btn_write_brd.setMinimumHeight(40)
        self.btn_write_brd.setStyleSheet("""
            QPushButton {
                background-color: #10b981; border: none; border-radius: 6px;
                color: white; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        left_layout.addWidget(self.btn_write_brd)
        
        # --- STEP 4: AUDIT RECONCILIATION ---
        step4_label = QLabel("STEP 4: AUDIT RECONCILIATION")
        step4_label.setStyleSheet("color: #ea580c; font-weight: bold; font-size: 11px; letter-spacing: 1px; margin-top: 12px;")
        left_layout.addWidget(step4_label)
        
        audit_frame = QFrame()
        audit_frame.setStyleSheet("background: #ffffff; border: 1px solid #fed7aa; border-radius: 6px;")
        audit_layout = QVBoxLayout(audit_frame)
        audit_layout.setContentsMargins(10, 10, 10, 10)
        audit_layout.setSpacing(8)
        
        # Audit description
        audit_desc = QLabel("📋 Load audited BRD to compare\ncounts after audit changes")
        audit_desc.setStyleSheet("color: #9a3412; font-size: 10px;")
        audit_desc.setWordWrap(True)
        audit_layout.addWidget(audit_desc)
        
        # Audited BRD File
        audit_file_row = QHBoxLayout()
        audit_file_row.addWidget(QLabel("📂 Audited BRD:"))
        self.btn_audit_brd = QPushButton("Select...")
        self.btn_audit_brd.clicked.connect(self.load_audit_brd)
        self.btn_audit_brd.setCursor(Qt.PointingHandCursor)
        self.btn_audit_brd.setMaximumWidth(80)
        self.btn_audit_brd.setStyleSheet("padding: 4px 10px; font-size: 10px; background-color: #ea580c; color: white; border-radius: 4px;")
        audit_file_row.addStretch()
        audit_file_row.addWidget(self.btn_audit_brd)
        audit_layout.addLayout(audit_file_row)
        
        self.lbl_audit_brd = QLabel("No file loaded")
        self.lbl_audit_brd.setStyleSheet("color: #94a3b8; font-size: 10px;")
        self.lbl_audit_brd.setWordWrap(True)
        audit_layout.addWidget(self.lbl_audit_brd)
        
        # Audit BRD Sheet
        audit_layout.addWidget(QLabel("Sheet:"))
        self.combo_audit_sheet = QComboBox()
        self.combo_audit_sheet.setPlaceholderText("Select...")
        audit_layout.addWidget(self.combo_audit_sheet)
        
        # Audit column selection via Spreadsheet Viewer
        self.btn_audit_select_col = QPushButton("🎯 Select Audited Column")
        self.btn_audit_select_col.clicked.connect(self.select_audit_column)
        self.btn_audit_select_col.setCursor(Qt.PointingHandCursor)
        self.btn_audit_select_col.setStyleSheet("""
            QPushButton {
                background-color: #ea580c;
                border: none; border-radius: 6px;
                color: white; font-weight: bold; font-size: 11px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #c2410c; }
        """)
        audit_layout.addWidget(self.btn_audit_select_col)
        
        # Audit column display
        audit_col_box = QFrame()
        audit_col_box.setStyleSheet("background: #fff7ed; border: 1px solid #fed7aa; border-radius: 4px;")
        audit_col_inner = QVBoxLayout(audit_col_box)
        audit_col_inner.setContentsMargins(8, 6, 8, 6)
        audit_col_inner.addWidget(QLabel("Audited Column:"))
        self.lbl_audit_col = QLabel("Not selected")
        self.lbl_audit_col.setStyleSheet("color: #ea580c; font-weight: bold; font-size: 10px;")
        self.lbl_audit_col.setWordWrap(True)
        audit_col_inner.addWidget(self.lbl_audit_col)
        audit_layout.addWidget(audit_col_box)
        
        # Recalculate button
        self.btn_recalculate = QPushButton("🔄 Recalculate & Compare")
        self.btn_recalculate.clicked.connect(self.run_audit_reconciliation)
        self.btn_recalculate.setCursor(Qt.PointingHandCursor)
        self.btn_recalculate.setMinimumHeight(40)
        self.btn_recalculate.setStyleSheet("""
            QPushButton {
                background-color: #ea580c; border: none; border-radius: 6px;
                color: white; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #c2410c; }
        """)
        audit_layout.addWidget(self.btn_recalculate)
        
        left_layout.addWidget(audit_frame)
        
        left_layout.addStretch()
        
        # === RIGHT PANEL (Table) ===
        right = QWidget()
        right.setStyleSheet("background-color: #ffffff;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 16, 20, 16)
        right_layout.setSpacing(12)
        splitter.addWidget(right)
        
        # Header
        header_row = QHBoxLayout()
        self.lbl_table_title = QLabel("📋 Asana CSV Data")
        self.lbl_table_title.setStyleSheet("color: #1e293b; font-size: 16px; font-weight: bold;")
        header_row.addWidget(self.lbl_table_title)
        header_row.addStretch()
        
        self.lbl_filter_count = QLabel("No data loaded")
        self.lbl_filter_count.setStyleSheet("color: #64748b; font-size: 12px;")
        header_row.addWidget(self.lbl_filter_count)
        right_layout.addLayout(header_row)
        
        # Status summary bar (GREEN/YELLOW/RED/NA counts)
        self.summary_bar = QWidget()
        summary_bar_layout = QHBoxLayout(self.summary_bar)
        summary_bar_layout.setContentsMargins(0, 0, 0, 0)
        summary_bar_layout.setSpacing(12)
        
        self.lbl_green_count = QLabel("🟢 GREEN: 0")
        self.lbl_green_count.setStyleSheet("color: #FFFFFF; background: #00B050; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        summary_bar_layout.addWidget(self.lbl_green_count)
        
        self.lbl_yellow_count = QLabel("🟡 YELLOW: 0")
        self.lbl_yellow_count.setStyleSheet("color: #000000; background: #FFFF00; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        summary_bar_layout.addWidget(self.lbl_yellow_count)
        
        self.lbl_red_count = QLabel("🔴 RED: 0")
        self.lbl_red_count.setStyleSheet("color: #FFFFFF; background: #FF0000; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        summary_bar_layout.addWidget(self.lbl_red_count)
        
        self.lbl_na_count = QLabel("⬜ NA: 0")
        self.lbl_na_count.setStyleSheet("color: #64748b; background: #e2e8f0; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        summary_bar_layout.addWidget(self.lbl_na_count)
        
        self.lbl_total_count = QLabel("📊 Total: 0")
        self.lbl_total_count.setStyleSheet("color: #FFFFFF; background: #475569; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        summary_bar_layout.addWidget(self.lbl_total_count)
        
        self.lbl_pass_fail = QLabel("")
        self.lbl_pass_fail.setStyleSheet("color: #475569; font-size: 11px; margin-left: 8px;")
        summary_bar_layout.addWidget(self.lbl_pass_fail)
        
        summary_bar_layout.addStretch()
        self.summary_bar.hide()
        right_layout.addWidget(self.summary_bar)
        
        # Table
        self.table = QTableView()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
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
                background-color: #f5f3ff;
                color: #475569;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #c4b5fd;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        
        self.table_model = CsvTableModel()
        self.table.setModel(self.table_model)
        
        # Install custom delegate for colored cells (same approach as BRD Viewer)
        self.cell_delegate = CsvCellDelegate(self.table_model, self.table)
        self.table.setItemDelegate(self.cell_delegate)
        right_layout.addWidget(self.table, 1)
        
        # Status bar
        self.lbl_status = QLabel("Ready — Import an Asana CSV to begin")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 11px; padding: 4px;")
        right_layout.addWidget(self.lbl_status)
        
        splitter.setSizes([320, 1080])
    
    # ====================
    # CSV IMPORT
    # ====================
    
    def import_csv(self):
        """Import Asana exported CSV file."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Import Asana CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not fname:
            return
        
        try:
            self.csv_file_path = fname
            df = CsvImporter.load_csv(fname)
            self.csv_data = CsvImporter.parse_asana_csv(df)
            
            # Enrich subtasks with parent info
            self.csv_data['tasks'] = CsvImporter.enrich_subtasks_with_parent_info(
                self.csv_data['tasks']
            )
            
            # Auto-calculate deviations and status
            self.csv_data['tasks'] = CsvImporter.calculate_deviations(
                self.csv_data['tasks']
            )
            
            # Update UI
            self.lbl_csv.setText(f"✓ {os.path.basename(fname)}")
            self.lbl_csv.setStyleSheet("color: #10b981; font-size: 11px;")
            
            summary = self.csv_data['summary']
            self.lbl_csv_summary.setText(
                f"{summary['total_rows']} rows • {summary['subtasks']} subtasks • "
                f"{summary['parent_tasks']} parent tasks • {summary['with_average']} with Average"
            )
            
            # Populate filter dropdowns
            self._populate_filters()
            
            # Apply initial filter (show all subtasks)
            self._apply_filters()
            
            self.lbl_status.setText(f"CSV loaded: {os.path.basename(fname)}")
            logger.info(f"CSV imported: {os.path.basename(fname)}")
            
        except Exception as e:
            logger.error(f"Failed to import CSV: {e}")
            QMessageBox.critical(self, "Import Error", f"Failed to import CSV:\n{str(e)}")
            self.lbl_csv.setText("❌ Error loading file")
            self.lbl_csv.setStyleSheet("color: #ef4444; font-size: 11px;")
    
    def _populate_filters(self):
        """Populate filter dropdowns from parsed CSV data."""
        if not self.csv_data:
            return
        
        # Parent Task
        self.combo_parent.blockSignals(True)
        self.combo_parent.clear()
        self.combo_parent.addItem("All")
        for pt in self.csv_data['parent_tasks']:
            self.combo_parent.addItem(pt)
        self.combo_parent.blockSignals(False)
        
        # Section
        self.combo_section.blockSignals(True)
        self.combo_section.clear()
        self.combo_section.addItem("All")
        for s in self.csv_data['sections']:
            if s:
                self.combo_section.addItem(s)
        self.combo_section.blockSignals(False)
        
        # Device
        self.combo_device.blockSignals(True)
        self.combo_device.clear()
        self.combo_device.addItem("All")
        for d in self.csv_data['devices']:
            if d:
                self.combo_device.addItem(d)
        self.combo_device.blockSignals(False)
    
    def _apply_filters(self):
        """Apply current filter settings to the table."""
        if not self.csv_data:
            return
        
        parent = self.combo_parent.currentText()
        section = self.combo_section.currentText()
        device = self.combo_device.currentText()
        search = self.inp_search.text().strip()
        
        self.filtered_tasks = CsvImporter.filter_tasks(
            self.csv_data['tasks'],
            parent_task=parent if parent != 'All' else None,
            section=section if section != 'All' else None,
            device=device if device != 'All' else None,
            search=search if search else None,
            subtasks_only=True
        )
        
        # Update table
        self.table_model.set_data(self.filtered_tasks)
        self.table.resizeColumnsToContents()
        
        # Update count
        total = self.csv_data['summary']['subtasks']
        shown = len(self.filtered_tasks)
        with_avg = sum(1 for t in self.filtered_tasks 
                      if t.get('Average', '') and t['Average'] not in ['', '-', '0'])
        
        self.lbl_filter_count.setText(f"{shown}/{total} tasks shown • {with_avg} with Average")
        
        # Update GREEN/YELLOW/RED/NA counts
        self._update_summary_counts()
        
        filters_active = []
        if parent != 'All':
            filters_active.append(f"Parent: {parent[:20]}")
        if section != 'All':
            filters_active.append(f"Section: {section[:20]}")
        if device != 'All':
            filters_active.append(f"Device: {device}")
        if search:
            filters_active.append(f"Search: '{search[:15]}'")
        
        if filters_active:
            self.lbl_status.setText(f"Filtered: {' | '.join(filters_active)}")
        else:
            self.lbl_status.setText(f"Showing all {shown} subtasks")
    
    def _update_summary_counts(self):
        """Update the GREEN/YELLOW/RED/NA count summary bar."""
        if not self.filtered_tasks:
            self.summary_bar.hide()
            return
        
        green = 0
        yellow = 0
        red = 0
        na = 0
        
        for t in self.filtered_tasks:
            avg = t.get('Average', '')
            if not avg or avg in ['', '-', '0']:
                na += 1
            else:
                color = t.get('_brd_color', '')
                if color == 'green':
                    green += 1
                elif color == 'yellow':
                    yellow += 1
                elif color == 'red':
                    red += 1
                else:
                    na += 1
        
        total_applicable = green + yellow + red
        pass_count = green + yellow
        fail_count = red
        
        self.lbl_green_count.setText(f"🟢 GREEN: {green}")
        self.lbl_yellow_count.setText(f"🟡 YELLOW: {yellow}")
        self.lbl_red_count.setText(f"🔴 RED: {red}")
        self.lbl_na_count.setText(f"⬜ NA: {na}")
        self.lbl_total_count.setText(f"📊 Total: {green + yellow + red + na}")
        
        if total_applicable > 0:
            pass_pct = (pass_count / total_applicable) * 100
            self.lbl_pass_fail.setText(
                f"PASS: {pass_count} | FAIL: {fail_count} | "
                f"Pass Rate: {pass_pct:.0f}%"
            )
        else:
            self.lbl_pass_fail.setText("")
        
        self.summary_bar.show()
    
    # ====================
    # BRD TARGET
    # ====================
    
    def load_brd(self):
        """Load BRD file for writing."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select BRD File", "", "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not fname:
            return
        
        try:
            self.brd_file_path = fname
            self.brd_sheets = DataLoader.load_all_sheets_as_raw(fname)
            
            self.lbl_brd.setText(f"✓ {os.path.basename(fname)}")
            self.lbl_brd.setStyleSheet("color: #10b981; font-size: 10px;")
            
            self.combo_brd_sheet.clear()
            for name, data in self.brd_sheets.items():
                row_count = len(data) - 1 if data else 0
                self.combo_brd_sheet.addItem(f"{name} ({row_count} rows)", name)
            
            self.lbl_status.setText(f"BRD loaded: {os.path.basename(fname)}")
            logger.info(f"BRD loaded for Report Generator: {os.path.basename(fname)}")
            
        except Exception as e:
            logger.error(f"Failed to load BRD: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load BRD:\n{str(e)}")
    
    def select_target_column(self):
        """Open Spreadsheet Viewer to select the target column in BRD."""
        sheet_name = self.combo_brd_sheet.currentData()
        
        if not self.brd_sheets or not sheet_name:
            QMessageBox.warning(self, "No BRD Data",
                "Please load a BRD file and select a sheet first.")
            return
        
        brd_data = self.brd_sheets.get(sheet_name, [])
        if not brd_data:
            QMessageBox.warning(self, "Empty Sheet", "Selected sheet has no data.")
            return
        
        # Import here to avoid circular imports
        from ui.brd_viewer_dialog import BrdViewerDialog
        
        dialog = BrdViewerDialog(brd_data, self, initial_search="",
                                 single_column_mode=True, 
                                 single_column_label="🎯 Target Column (where to write Average)")
        
        if dialog.exec_():
            selection = dialog.get_selection()
            
            # Use the Perf column selection as the target column
            self.selected_target_col = {
                "name": selection['perf'].get('name', ''),
                "columnIndex": selection['perf'].get('index', -1)
            }
            
            col_name = self.selected_target_col['name']
            col_idx = self.selected_target_col['columnIndex']
            
            if col_idx >= 0:
                self.lbl_target_col.setText(f"Col {col_idx}: {col_name[:30]}")
                self.lbl_target_col.setStyleSheet("color: #7c3aed; font-weight: bold; font-size: 10px;")
                self.lbl_status.setText(f"Target column selected: {col_name}")
            else:
                self.lbl_target_col.setText("Not selected")
    
    # ====================
    # WRITE TO BRD
    # ====================
    
    def preview_write(self):
        """Preview what would be written to BRD (dry run) — shows full table."""
        result = self._execute_write(dry_run=True)
        if result is None:
            return
        
        matched = result['matched']
        unmatched = result['unmatched']
        
        if not matched and not unmatched:
            QMessageBox.information(self, "Preview", "No tasks with Average values to write.")
            return
        
        # Show a proper preview dialog with table
        from PyQt5.QtWidgets import QDialog, QTableWidget, QTableWidgetItem
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"📋 Write Preview — {len(matched)} matched, {len(unmatched)} unmatched")
        dialog.setMinimumSize(1000, 600)
        dlg_layout = QVBoxLayout(dialog)
        
        # Summary
        summary = QLabel(f"✅ <b>{len(matched)}</b> scenarios will be updated  |  "
                        f"⚠️ <b>{len(unmatched)}</b> unmatched (skipped)")
        summary.setStyleSheet("font-size: 14px; padding: 8px; background: #f1f5f9; border-radius: 6px;")
        dlg_layout.addWidget(summary)
        
        # Matched table
        if matched:
            dlg_layout.addWidget(QLabel(f"<b>✅ Matched ({len(matched)}):</b>"))
            
            match_table = QTableWidget(len(matched), 5)
            match_table.setHorizontalHeaderLabels(["Scenario", "Parent Task", "Old Value", "New Value (Average)", "BRD Row"])
            match_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            match_table.setAlternatingRowColors(True)
            match_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            match_table.setStyleSheet("QTableWidget { gridline-color: #e2e8f0; } "
                                     "QTableWidget::item { padding: 4px; }")
            
            for i, m in enumerate(matched):
                match_table.setItem(i, 0, QTableWidgetItem(m['scenario']))
                match_table.setItem(i, 1, QTableWidgetItem(m.get('parent', '')))
                
                old_item = QTableWidgetItem(m['old_value'])
                old_item.setBackground(QColor('#fef3c7'))
                match_table.setItem(i, 2, old_item)
                
                new_item = QTableWidgetItem(m['new_value'])
                new_item.setBackground(QColor('#ecfdf5'))
                match_table.setItem(i, 3, new_item)
                
                match_table.setItem(i, 4, QTableWidgetItem(str(m.get('brd_row', ''))))
            
            match_table.resizeColumnsToContents()
            dlg_layout.addWidget(match_table, 1)
        
        # Unmatched table
        if unmatched:
            dlg_layout.addWidget(QLabel(f"<b>⚠️ Unmatched ({len(unmatched)}) — these will be skipped:</b>"))
            
            unmatch_table = QTableWidget(len(unmatched), 3)
            unmatch_table.setHorizontalHeaderLabels(["Scenario", "Parent Task", "Average"])
            unmatch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            unmatch_table.setAlternatingRowColors(True)
            unmatch_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            unmatch_table.setMaximumHeight(200)
            unmatch_table.setStyleSheet("QTableWidget { gridline-color: #fecaca; } "
                                       "QTableWidget::item { padding: 4px; background: #fef2f2; }")
            
            for i, u in enumerate(unmatched):
                unmatch_table.setItem(i, 0, QTableWidgetItem(u['scenario']))
                unmatch_table.setItem(i, 1, QTableWidgetItem(u.get('parent', '')))
                unmatch_table.setItem(i, 2, QTableWidgetItem(u.get('average', '')))
            
            unmatch_table.resizeColumnsToContents()
            dlg_layout.addWidget(unmatch_table)
        
        # Close button
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        btn_close.setStyleSheet("padding: 8px 24px; background: #3b82f6; color: white; border-radius: 6px; font-weight: bold;")
        dlg_layout.addWidget(btn_close, alignment=Qt.AlignRight)
        
        dialog.exec_()
    
    def write_to_brd(self):
        """Write Average values to BRD file."""
        result = self._execute_write(dry_run=True)
        if result is None:
            return
        
        matched = result['matched']
        if not matched:
            QMessageBox.warning(self, "No Matches", "No scenarios matched. Nothing to write.")
            return
        
        # Confirm
        reply = QMessageBox.question(self, "Confirm Write",
            f"Write {len(matched)} Average values to BRD file?\n\n"
            f"File: {os.path.basename(self.brd_file_path)}\n"
            f"Sheet: {self.combo_brd_sheet.currentData()}\n"
            f"Column: {self.selected_target_col['name']}\n\n"
            f"This will modify the BRD file.",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        # Ask for output file (save as)
        default_name = os.path.splitext(self.brd_file_path)[0] + "_updated.xlsx"
        fname, _ = QFileDialog.getSaveFileName(
            self, "Save Updated BRD File", default_name, "Excel Files (*.xlsx)"
        )
        if not fname:
            return
        
        # Execute actual write
        result = self._execute_write(dry_run=False, output_path=fname)
        if result:
            QMessageBox.information(self, "Write Complete",
                f"✅ Successfully wrote {result['total_written']} values!\n\n"
                f"Saved to: {os.path.basename(fname)}\n"
                f"Unmatched: {result['total_skipped']}")
            self.lbl_status.setText(f"✅ Wrote {result['total_written']} values to {os.path.basename(fname)}")
    
    def _execute_write(self, dry_run=True, output_path=None):
        """Execute the write operation (or dry run)."""
        # Validate inputs
        if not self.filtered_tasks:
            QMessageBox.warning(self, "No Data", "No filtered tasks to write. Import a CSV first.")
            return None
        
        if not self.brd_file_path:
            QMessageBox.warning(self, "No BRD File", "Please load a BRD file first.")
            return None
        
        sheet_name = self.combo_brd_sheet.currentData()
        if not sheet_name:
            QMessageBox.warning(self, "No Sheet", "Please select a BRD sheet.")
            return None
        
        target_col = self.selected_target_col.get('columnIndex', -1)
        if target_col < 0:
            QMessageBox.warning(self, "No Target Column", 
                "Please select a target column in the BRD file using the Spreadsheet Viewer.")
            return None
        
        # Find the scenario column in BRD (nearest to target column)
        brd_data = self.brd_sheets.get(sheet_name, [])
        if not brd_data:
            QMessageBox.warning(self, "Empty BRD Sheet", "Selected BRD sheet has no data.")
            return None
        
        # Auto-detect scenario column in BRD
        from core.brd_matcher import BrdMatcher
        matcher = BrdMatcher()
        
        scan_rows = brd_data[:10]
        
        def is_scenario_col(h):
            h_str = str(h or '').lower()
            return ('performance scenario' in h_str or 
                    'performance scanrio' in h_str or
                    'scenario name' in h_str or
                    h_str == 'name')
        
        # Find all scenario columns and pick nearest to target
        scenario_cols = set()
        for row in scan_rows:
            for c_idx, val in enumerate(row):
                if is_scenario_col(val):
                    scenario_cols.add(c_idx)
        
        if not scenario_cols:
            QMessageBox.warning(self, "No Scenario Column", 
                "Could not find 'Performance Scenario' column in BRD sheet.")
            return None
        
        # Pick scenario column closest to (and before) target column
        sorted_cols = sorted(scenario_cols)
        before = [c for c in sorted_cols if c < target_col]
        scenario_col = before[-1] if before else sorted_cols[0]
        
        logger.info(f"Write operation: scenario_col={scenario_col}, target_col={target_col}, "
                    f"sheet='{sheet_name}', tasks={len(self.filtered_tasks)}, dry_run={dry_run}")
        
        try:
            writer = BrdWriter()
            result = writer.write_averages_to_brd(
                brd_file_path=self.brd_file_path,
                sheet_name=sheet_name,
                target_col_index=target_col,
                scenario_col_index=scenario_col,
                csv_tasks=self.filtered_tasks,
                output_path=output_path,
                dry_run=dry_run
            )
            return result
            
        except Exception as e:
            logger.error(f"Write operation failed: {e}")
            QMessageBox.critical(self, "Write Error", f"Failed to write to BRD:\n{str(e)}")
            return None

    # ====================
    # AUDIT RECONCILIATION
    # ====================

    def _detect_scenario_column(self, brd_data, target_col_index):
        """
        Auto-detect the scenario column in BRD data (nearest to and before target column).
        Returns the scenario column index or -1 if not found.
        """
        scan_rows = brd_data[:10]

        def is_scenario_col(h):
            h_str = str(h or '').lower()
            return ('performance scenario' in h_str or
                    'performance scanrio' in h_str or
                    'scenario name' in h_str or
                    h_str == 'name')

        scenario_cols = set()
        for row in scan_rows:
            for c_idx, val in enumerate(row):
                if is_scenario_col(val):
                    scenario_cols.add(c_idx)

        if not scenario_cols:
            return -1

        sorted_cols = sorted(scenario_cols)
        before = [c for c in sorted_cols if c < target_col_index]
        return before[-1] if before else sorted_cols[0]

    def load_audit_brd(self):
        """Load the audited BRD file for reconciliation."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Audited BRD File", "", "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not fname:
            return

        try:
            self.audit_brd_file_path = fname
            self.audit_brd_sheets = DataLoader.load_all_sheets_as_raw(fname)

            self.lbl_audit_brd.setText(f"✓ {os.path.basename(fname)}")
            self.lbl_audit_brd.setStyleSheet("color: #ea580c; font-size: 10px; font-weight: bold;")

            self.combo_audit_sheet.clear()
            for name, data in self.audit_brd_sheets.items():
                row_count = len(data) - 1 if data else 0
                self.combo_audit_sheet.addItem(f"{name} ({row_count} rows)", name)

            self.lbl_status.setText(f"Audited BRD loaded: {os.path.basename(fname)}")
            logger.info(f"Audited BRD loaded: {os.path.basename(fname)}")

        except Exception as e:
            logger.error(f"Failed to load audited BRD: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load audited BRD:\n{str(e)}")

    def select_audit_column(self):
        """Open Spreadsheet Viewer to select the audited Average column."""
        sheet_name = self.combo_audit_sheet.currentData()

        if not self.audit_brd_sheets or not sheet_name:
            QMessageBox.warning(self, "No Audited BRD Data",
                "Please load an audited BRD file and select a sheet first.")
            return

        brd_data = self.audit_brd_sheets.get(sheet_name, [])
        if not brd_data:
            QMessageBox.warning(self, "Empty Sheet", "Selected sheet has no data.")
            return

        from ui.brd_viewer_dialog import BrdViewerDialog

        dialog = BrdViewerDialog(brd_data, self, initial_search="",
                                 single_column_mode=True,
                                 single_column_label="🎯 Audited Average Column")

        if dialog.exec_():
            selection = dialog.get_selection()
            self.audit_selected_col = {
                "name": selection['perf'].get('name', ''),
                "columnIndex": selection['perf'].get('index', -1)
            }

            col_name = self.audit_selected_col['name']
            col_idx = self.audit_selected_col['columnIndex']

            if col_idx >= 0:
                self.lbl_audit_col.setText(f"Col {col_idx}: {col_name[:30]}")
                self.lbl_audit_col.setStyleSheet("color: #ea580c; font-weight: bold; font-size: 10px;")
                self.lbl_status.setText(f"Audited column selected: {col_name}")
            else:
                self.lbl_audit_col.setText("Not selected")

    def run_audit_reconciliation(self):
        """
        Run the audit reconciliation:
        1. Read audited values from BRD using scenario matching
        2. Compare with original CSV Average values
        3. Recalculate deviations and colors
        4. Show comparison dialog
        """
        # Validate prerequisites
        if not self.filtered_tasks:
            QMessageBox.warning(self, "No CSV Data",
                "Please import a CSV and filter data first (Steps 1-2).")
            return

        if not self.audit_brd_sheets:
            QMessageBox.warning(self, "No Audited BRD",
                "Please load an audited BRD file first.")
            return

        audit_sheet_name = self.combo_audit_sheet.currentData()
        if not audit_sheet_name:
            QMessageBox.warning(self, "No Sheet", "Please select an audited BRD sheet.")
            return

        audit_col_idx = self.audit_selected_col.get('columnIndex', -1)
        if audit_col_idx < 0:
            QMessageBox.warning(self, "No Audited Column",
                "Please select the audited Average column via Spreadsheet Viewer.")
            return

        audit_brd_data = self.audit_brd_sheets.get(audit_sheet_name, [])
        if not audit_brd_data:
            QMessageBox.warning(self, "Empty Sheet", "Audited BRD sheet has no data.")
            return

        # Auto-detect scenario column in audited BRD
        scenario_col_idx = self._detect_scenario_column(audit_brd_data, audit_col_idx)
        if scenario_col_idx < 0:
            QMessageBox.warning(self, "No Scenario Column",
                "Could not find 'Performance Scenario' column in audited BRD sheet.")
            return

        try:
            self._execute_reconciliation(audit_brd_data, audit_sheet_name,
                                          scenario_col_idx, audit_col_idx)
        except Exception as e:
            logger.error(f"Audit reconciliation failed: {e}")
            QMessageBox.critical(self, "Reconciliation Error",
                f"Failed to run audit reconciliation:\n{str(e)}")

    def _execute_reconciliation(self, audit_brd_data, audit_sheet_name,
                                 scenario_col_idx, audit_col_idx):
        """Execute the reconciliation logic and show the comparison dialog."""
        matcher = BrdMatcher()

        # Build scenario lookup from audited BRD
        scenario_lookup = BrdWriter.build_scenario_lookup(audit_brd_data, scenario_col_idx)
        logger.info(f"Audit reconciliation: {len(scenario_lookup)} scenarios in audited BRD")

        # Read audited BRD rows for value extraction
        import openpyxl
        wb = openpyxl.load_workbook(self.audit_brd_file_path, data_only=True, read_only=True)
        ws = wb[audit_sheet_name]
        brd_rows = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            brd_rows.append(list(row))
        wb.close()

        # Capture original counts BEFORE reconciliation
        orig_green, orig_yellow, orig_red, orig_na = 0, 0, 0, 0
        for t in self.filtered_tasks:
            avg = t.get('Average', '')
            if not avg or avg in ['', '-', '0']:
                orig_na += 1
            else:
                color = t.get('_brd_color', '')
                if color == 'green':
                    orig_green += 1
                elif color == 'yellow':
                    orig_yellow += 1
                elif color == 'red':
                    orig_red += 1
                else:
                    orig_na += 1

        self.original_counts = {
            'green': orig_green, 'yellow': orig_yellow,
            'red': orig_red, 'na': orig_na
        }

        # Match CSV tasks to audited BRD and read new values
        comparison_data = []
        scenario_match_count = {}
        matched_count = 0
        unmatched_count = 0

        for task in self.filtered_tasks:
            scenario_name = task.get('Name', '')
            original_avg_str = task.get('Average', '')
            perf_brd_str = task.get('Perf_BRD', '')
            parent = task.get('Parent task', '')
            original_color = task.get('_brd_color', '')

            normalized = matcher.normalize_scenario_name(scenario_name)

            comp = {
                'scenario': scenario_name,
                'parent': parent,
                'original_avg': original_avg_str,
                'audited_avg': '',
                'perf_brd': perf_brd_str,
                'original_color': original_color,
                'audited_color': '',
                'original_status': task.get('BRD Status', ''),
                'audited_status': '',
                'changed': False,
                'matched': False,
            }

            if normalized in scenario_lookup:
                brd_rows_list = scenario_lookup[normalized]
                occurrence = scenario_match_count.get(normalized, 0)

                if occurrence < len(brd_rows_list):
                    row_num = brd_rows_list[occurrence]
                    scenario_match_count[normalized] = occurrence + 1
                    row_idx = row_num - 1  # 0-based

                    # Read the audited value
                    audited_val = None
                    if row_idx < len(brd_rows) and audit_col_idx < len(brd_rows[row_idx]):
                        audited_val = brd_rows[row_idx][audit_col_idx]

                    audited_avg_str = str(audited_val) if audited_val is not None else ''
                    if audited_avg_str.lower() in ['none', 'nan', '']:
                        audited_avg_str = ''

                    comp['audited_avg'] = audited_avg_str
                    comp['matched'] = True
                    matched_count += 1

                    # Recalculate deviation and color for audited value
                    audited_num = CsvImporter._parse_number(audited_avg_str)
                    perf_brd_num = CsvImporter._parse_number(perf_brd_str)

                    if audited_num is not None and perf_brd_num is not None and perf_brd_num != 0:
                        dev = (audited_num - perf_brd_num) / perf_brd_num
                        comp['audited_color'] = CsvImporter._get_color(dev)
                        comp['audited_status'] = CsvImporter._get_status(dev)
                    else:
                        comp['audited_color'] = ''
                        comp['audited_status'] = ''

                    # Detect change
                    comp['changed'] = (comp['original_color'] != comp['audited_color']
                                       and comp['audited_color'] != '')
                else:
                    unmatched_count += 1
            else:
                unmatched_count += 1

            comparison_data.append(comp)

        self.audit_comparison_data = comparison_data

        # Calculate audited counts
        aud_green, aud_yellow, aud_red, aud_na = 0, 0, 0, 0
        for c in comparison_data:
            if c['matched'] and c['audited_avg']:
                color = c['audited_color']
                if color == 'green':
                    aud_green += 1
                elif color == 'yellow':
                    aud_yellow += 1
                elif color == 'red':
                    aud_red += 1
                else:
                    aud_na += 1
            else:
                aud_na += 1

        self.audited_counts = {
            'green': aud_green, 'yellow': aud_yellow,
            'red': aud_red, 'na': aud_na
        }

        changed_count = sum(1 for c in comparison_data if c['changed'])

        logger.info(f"Audit reconciliation complete: {matched_count} matched, "
                    f"{unmatched_count} unmatched, {changed_count} changed")

        self.lbl_status.setText(
            f"🔄 Audit: {matched_count} matched, {changed_count} changed | "
            f"Before: G{orig_green}/Y{orig_yellow}/R{orig_red} → "
            f"After: G{aud_green}/Y{aud_yellow}/R{aud_red}"
        )

        # Show comparison dialog
        self._show_audit_comparison_dialog(comparison_data, matched_count,
                                            unmatched_count, changed_count)

    def _show_audit_comparison_dialog(self, comparison_data, matched_count,
                                       unmatched_count, changed_count):
        """Show the audit comparison dialog with before/after summary and detailed table."""
        from PyQt5.QtWidgets import (QDialog, QTableWidget, QTableWidgetItem,
                                     QTabWidget)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"🔄 Audit Reconciliation — {matched_count} matched, {changed_count} changed")
        dialog.setMinimumSize(1200, 700)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(12)
        dlg_layout.setContentsMargins(20, 20, 20, 20)

        # === SUMMARY: BEFORE / AFTER / DELTA ===
        summary_widget = QWidget()
        summary_widget.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;")
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        summary_layout.setSpacing(8)

        summary_title = QLabel("📊 Audit Reconciliation Summary")
        summary_title.setStyleSheet("color: #1e293b; font-size: 16px; font-weight: bold; border: none;")
        summary_layout.addWidget(summary_title)

        # Three rows: BEFORE, AFTER, DELTA
        oc = self.original_counts
        ac = self.audited_counts

        def make_count_row(label, green, yellow, red, na, is_delta=False):
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(f"<b>{label}</b>")
            lbl.setMinimumWidth(80)
            lbl.setStyleSheet("color: #475569; font-size: 13px; border: none;")
            row.addWidget(lbl)

            prefix = lambda v: f"+{v}" if v > 0 and is_delta else str(v)

            g = QLabel(f"🟢 GREEN: {prefix(green)}")
            g.setStyleSheet("color: #FFFFFF; background: #00B050; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;")
            row.addWidget(g)

            y = QLabel(f"🟡 YELLOW: {prefix(yellow)}")
            y.setStyleSheet("color: #000000; background: #FFFF00; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;")
            row.addWidget(y)

            r = QLabel(f"🔴 RED: {prefix(red)}")
            r.setStyleSheet("color: #FFFFFF; background: #FF0000; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;")
            row.addWidget(r)

            n = QLabel(f"⬜ NA: {prefix(na)}")
            n.setStyleSheet("color: #64748b; background: #e2e8f0; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;")
            row.addWidget(n)

            total = green + yellow + red + na
            t = QLabel(f"📊 Total: {total}")
            t.setStyleSheet("color: #FFFFFF; background: #475569; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;")
            row.addWidget(t)

            row.addStretch()
            return row

        summary_layout.addLayout(make_count_row("BEFORE:",
            oc['green'], oc['yellow'], oc['red'], oc['na']))
        summary_layout.addLayout(make_count_row("AFTER:",
            ac['green'], ac['yellow'], ac['red'], ac['na']))

        delta_g = ac['green'] - oc['green']
        delta_y = ac['yellow'] - oc['yellow']
        delta_r = ac['red'] - oc['red']
        delta_na = ac['na'] - oc['na']
        summary_layout.addLayout(make_count_row("DELTA:",
            delta_g, delta_y, delta_r, delta_na, is_delta=True))

        # Pass rate comparison
        orig_applicable = oc['green'] + oc['yellow'] + oc['red']
        aud_applicable = ac['green'] + ac['yellow'] + ac['red']
        orig_pass_rate = ((oc['green'] + oc['yellow']) / orig_applicable * 100) if orig_applicable > 0 else 0
        aud_pass_rate = ((ac['green'] + ac['yellow']) / aud_applicable * 100) if aud_applicable > 0 else 0

        pass_info = QLabel(
            f"Pass Rate: <b>{orig_pass_rate:.0f}%</b> → <b>{aud_pass_rate:.0f}%</b>  |  "
            f"Matched: {matched_count}  |  Unmatched: {unmatched_count}  |  "
            f"Changed: <b style='color: #ea580c;'>{changed_count}</b>"
        )
        pass_info.setStyleSheet("color: #475569; font-size: 13px; padding: 4px; border: none;")
        summary_layout.addWidget(pass_info)

        dlg_layout.addWidget(summary_widget)

        # === FILTER BAR ===
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Filter:"))
        combo_filter = QComboBox()
        combo_filter.addItems(["All Scenarios", "Changed Only", "Unchanged Only",
                               "GREEN → YELLOW", "GREEN → RED",
                               "YELLOW → RED", "YELLOW → GREEN",
                               "RED → YELLOW", "RED → GREEN"])
        filter_bar.addWidget(combo_filter)
        filter_bar.addStretch()
        dlg_layout.addLayout(filter_bar)

        # === COMPARISON TABLE ===
        columns = ["Scenario", "Parent Task", "Original Avg", "Audited Avg",
                    "Perf BRD", "Original Color", "Audited Color", "Status", "Changed"]
        comp_table = QTableWidget(len(comparison_data), len(columns))
        comp_table.setHorizontalHeaderLabels(columns)
        comp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        comp_table.setAlternatingRowColors(True)
        comp_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        comp_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        comp_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e2e8f0;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section {
                background-color: #fff7ed;
                color: #9a3412;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #fed7aa;
                font-weight: bold;
            }
        """)

        color_map = {
            'green': ('#00B050', '#FFFFFF'),
            'yellow': ('#FFFF00', '#000000'),
            'red': ('#FF0000', '#FFFFFF'),
        }

        def populate_table(data):
            comp_table.setRowCount(len(data))
            for i, c in enumerate(data):
                comp_table.setItem(i, 0, QTableWidgetItem(c['scenario']))
                comp_table.setItem(i, 1, QTableWidgetItem(c['parent']))
                comp_table.setItem(i, 2, QTableWidgetItem(c['original_avg']))
                comp_table.setItem(i, 3, QTableWidgetItem(c['audited_avg']))
                comp_table.setItem(i, 4, QTableWidgetItem(c['perf_brd']))

                # Original color cell
                orig_item = QTableWidgetItem(c['original_color'].upper() if c['original_color'] else 'NA')
                if c['original_color'] in color_map:
                    bg, fg = color_map[c['original_color']]
                    orig_item.setBackground(QColor(bg))
                    orig_item.setForeground(QColor(fg))
                comp_table.setItem(i, 5, orig_item)

                # Audited color cell
                aud_item = QTableWidgetItem(c['audited_color'].upper() if c['audited_color'] else 'NA')
                if c['audited_color'] in color_map:
                    bg, fg = color_map[c['audited_color']]
                    aud_item.setBackground(QColor(bg))
                    aud_item.setForeground(QColor(fg))
                comp_table.setItem(i, 6, aud_item)

                # Status
                status_text = c.get('audited_status', '') or c.get('original_status', '')
                comp_table.setItem(i, 7, QTableWidgetItem(status_text))

                # Changed indicator
                changed_item = QTableWidgetItem("⚠️ YES" if c['changed'] else "—")
                if c['changed']:
                    changed_item.setBackground(QColor('#fef3c7'))
                    changed_item.setForeground(QColor('#92400e'))
                comp_table.setItem(i, 8, changed_item)

            comp_table.resizeColumnsToContents()

        populate_table(comparison_data)

        def on_filter_changed(filter_text):
            if filter_text == "All Scenarios":
                filtered = comparison_data
            elif filter_text == "Changed Only":
                filtered = [c for c in comparison_data if c['changed']]
            elif filter_text == "Unchanged Only":
                filtered = [c for c in comparison_data if not c['changed']]
            elif "→" in filter_text:
                parts = filter_text.split("→")
                from_color = parts[0].strip().lower()
                to_color = parts[1].strip().lower()
                filtered = [c for c in comparison_data
                           if c['original_color'] == from_color
                           and c['audited_color'] == to_color]
            else:
                filtered = comparison_data
            populate_table(filtered)

        combo_filter.currentTextChanged.connect(on_filter_changed)

        dlg_layout.addWidget(comp_table, 1)

        # === CLOSE BUTTON ===
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("padding: 10px 30px; background: #3b82f6; color: white; "
                                "border-radius: 6px; font-weight: bold; font-size: 13px;")
        btn_row.addWidget(btn_close)
        dlg_layout.addLayout(btn_row)

        dialog.exec_()
