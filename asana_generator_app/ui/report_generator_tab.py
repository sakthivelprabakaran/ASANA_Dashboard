"""
Report Generator Tab - Import Asana CSV, filter tasks, and write Average values back to BRD.
"""

import os
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFileDialog, QComboBox, QLineEdit, QTableView, QHeaderView,
                             QMessageBox, QFrame, QScrollArea, QSplitter, QAbstractItemView)
from PyQt5.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QTimer
from PyQt5.QtGui import QColor

from core.csv_importer import CsvImporter
from core.brd_writer import BrdWriter
from core.data_loader import DataLoader

logger = logging.getLogger('AsanaGenerator.ReportGenerator')


class CsvTableModel(QAbstractTableModel):
    """Table model for displaying filtered CSV task data."""
    
    DISPLAY_COLUMNS = [
        'Parent task', 'Name', 'Devices', 'Average', 'Perf_BRD', 
        'Previous Value', 'Priority', 'BRD Status', 'Previous Status',
        'Deviation_BRD', 'Deviation_Prev', 'Assignee', 'Task Progress'
    ]
    
    COLUMN_LABELS = {
        'Parent task': 'Parent Task',
        'Name': 'Scenario',
        'Devices': 'Device',
        'Average': 'Average',
        'Perf_BRD': 'Perf BRD',
        'Previous Value': 'Previous',
        'Priority': 'Priority',
        'BRD Status': 'BRD Status',
        'Previous Status': 'Prev Status',
        'Deviation_BRD': 'Dev% BRD',
        'Deviation_Prev': 'Dev% Prev',
        'Assignee': 'Assignee',
        'Task Progress': 'Progress',
    }

    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
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
            # Highlight BRD Status
            if col_key == 'BRD Status':
                val_lower = str(val).lower()
                if 'red' in val_lower:
                    return QColor('#fee2e2')
                elif 'yellow' in val_lower:
                    return QColor('#fef3c7')
                elif 'green' in val_lower:
                    return QColor('#ecfdf5')
        
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
