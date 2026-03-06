"""
Manual Subtask Dialog - Popup for managing ad-hoc test case subtasks.
Provides a spacious table view for adding/removing manual subtasks
with Name, Priority, Est. Time, N-Points, Previous Value, and Perf BRD fields.
Supports bulk import from Excel via the ExcelImportDialog.
"""

import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QAbstractItemView, QFrame)
from PyQt5.QtCore import Qt

logger = logging.getLogger('AsanaGenerator.ManualSubtaskDialog')


class ManualSubtaskDialog(QDialog):
    """
    Dialog for managing manual subtasks (ad-hoc testing).
    Shows a table with Name, Priority, Est. Time, N-Points, Previous Value, Perf BRD columns.
    Subtasks are edited in-place and returned when dialog is accepted.
    Supports both one-by-one entry and bulk Excel import.
    """

    # Column definitions for the table
    COL_DEFS = [
        {"key": "name",           "header": "Subtask Name",    "stretch": True,  "width": 0},
        {"key": "priority",       "header": "Priority",        "stretch": False, "width": 80},
        {"key": "est_time",       "header": "Est. Time",       "stretch": False, "width": 80},
        {"key": "n_points",       "header": "N-Points",        "stretch": False, "width": 90},
        {"key": "previous_value", "header": "Previous Value",  "stretch": False, "width": 110},
        {"key": "perf_brd",       "header": "Perf BRD",        "stretch": False, "width": 100},
    ]
    # Extra action column for delete button
    ACTION_COL_WIDTH = 60

    def __init__(self, subtasks=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔧 Manual Subtasks — Ad-Hoc Testing")
        self.setMinimumSize(950, 560)
        self.resize(1050, 620)

        # Working copy of subtasks
        self._subtasks = list(subtasks) if subtasks else []

        self._init_ui()
        self._load_subtasks()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("📝 Add manual test cases (ad-hoc subtasks)")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b;")
        layout.addWidget(header)

        desc = QLabel("These subtasks will be added to your queue entry. "
                       "You can add them one-by-one below or bulk import from an Excel file.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 12px; margin-bottom: 4px;")
        layout.addWidget(desc)

        # ── Import from Excel button ──
        import_frame = QFrame()
        import_frame.setStyleSheet("background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;")
        import_layout = QHBoxLayout(import_frame)
        import_layout.setContentsMargins(14, 10, 14, 10)
        import_layout.setSpacing(10)

        import_icon = QLabel("📥")
        import_icon.setStyleSheet("font-size: 20px;")
        import_layout.addWidget(import_icon)

        import_text = QVBoxLayout()
        import_text.setSpacing(2)
        import_title = QLabel("Bulk Import from Excel")
        import_title.setStyleSheet("font-weight: bold; color: #1e40af; font-size: 13px;")
        import_text.addWidget(import_title)
        import_desc = QLabel("Import Test Cases, N-Points, Previous Values, Perf BRD columns from a spreadsheet")
        import_desc.setStyleSheet("color: #3b82f6; font-size: 11px;")
        import_text.addWidget(import_desc)
        import_layout.addLayout(import_text, 1)

        btn_import = QPushButton("📥 Import from Excel…")
        btn_import.clicked.connect(self._open_excel_import)
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.setStyleSheet("padding: 10px 20px; background: #3b82f6; color: white; "
                                  "border-radius: 6px; font-weight: bold; font-size: 13px; border: none;")
        import_layout.addWidget(btn_import)

        layout.addWidget(import_frame)

        # ── Single-entry input row ──
        input_frame = QFrame()
        input_frame.setStyleSheet("background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px;")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(14, 10, 14, 10)
        input_layout.setSpacing(8)

        # Name input
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Subtask Name:"))
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("e.g., Check WiFi reconnect after OTA update")
        self.inp_name.setStyleSheet("padding: 8px; font-size: 13px; border: 1px solid #e2e8f0; border-radius: 6px;")
        self.inp_name.returnPressed.connect(self._add_subtask)
        name_row.addWidget(self.inp_name, 1)
        input_layout.addLayout(name_row)

        # Detail fields + Add button
        detail_row = QHBoxLayout()
        detail_row.setSpacing(10)

        detail_row.addWidget(QLabel("Priority:"))
        self.inp_priority = QLineEdit()
        self.inp_priority.setPlaceholderText("optional")
        self.inp_priority.setMaximumWidth(100)
        self.inp_priority.setStyleSheet("padding: 6px; border: 1px solid #e2e8f0; border-radius: 4px;")
        detail_row.addWidget(self.inp_priority)

        detail_row.addWidget(QLabel("Est. Time:"))
        self.inp_time = QLineEdit()
        self.inp_time.setPlaceholderText("optional")
        self.inp_time.setMaximumWidth(100)
        self.inp_time.setStyleSheet("padding: 6px; border: 1px solid #e2e8f0; border-radius: 4px;")
        self.inp_time.returnPressed.connect(self._add_subtask)
        detail_row.addWidget(self.inp_time)

        detail_row.addStretch()

        btn_add = QPushButton("➕ Add Subtask")
        btn_add.clicked.connect(self._add_subtask)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet("padding: 8px 20px; background: #f59e0b; color: white; "
                              "border-radius: 6px; font-weight: bold; font-size: 13px;")
        detail_row.addWidget(btn_add)

        input_layout.addLayout(detail_row)
        layout.addWidget(input_frame)

        # Count label
        self.lbl_count = QLabel("📝 0 subtasks")
        self.lbl_count.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.lbl_count)

        # ── Table ──
        total_cols = len(self.COL_DEFS) + 1  # +1 for delete action column
        self.table = QTableWidget()
        self.table.setColumnCount(total_cols)

        headers = [c["header"] for c in self.COL_DEFS] + [""]
        self.table.setHorizontalHeaderLabels(headers)

        for i, cdef in enumerate(self.COL_DEFS):
            if cdef["stretch"]:
                self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Fixed)
                self.table.setColumnWidth(i, cdef["width"])

        # Action column (delete)
        action_idx = len(self.COL_DEFS)
        self.table.horizontalHeader().setSectionResizeMode(action_idx, QHeaderView.Fixed)
        self.table.setColumnWidth(action_idx, self.ACTION_COL_WIDTH)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #f1f5f9;
                font-size: 12px;
            }
            QTableWidget::item { padding: 6px 8px; }
            QHeaderView::section {
                background: #fffbeb;
                color: #92400e;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #fcd34d;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.table, 1)

        # ── Bottom buttons ──
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        btn_clear = QPushButton("🗑️ Clear All")
        btn_clear.clicked.connect(self._clear_all)
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet("padding: 8px 16px; background: #fee2e2; color: #dc2626; "
                                "border: 1px solid #fecaca; border-radius: 6px; font-weight: bold;")
        bottom_row.addWidget(btn_clear)

        bottom_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("padding: 8px 20px; background: #f1f5f9; color: #475569; "
                                 "border: 1px solid #e2e8f0; border-radius: 6px; font-weight: bold;")
        bottom_row.addWidget(btn_cancel)

        btn_done = QPushButton("✅ Done")
        btn_done.clicked.connect(self.accept)
        btn_done.setCursor(Qt.PointingHandCursor)
        btn_done.setStyleSheet("padding: 8px 24px; background: #10b981; color: white; "
                               "border: none; border-radius: 6px; font-weight: bold; font-size: 13px;")
        bottom_row.addWidget(btn_done)

        layout.addLayout(bottom_row)

    # ─────────────────── Table helpers ───────────────────

    def _load_subtasks(self):
        """Rebuild the table from self._subtasks."""
        self.table.setRowCount(0)
        for subtask in self._subtasks:
            self._add_row(subtask)
        self._update_count()

    def _add_row(self, subtask: dict):
        """Add a single row to the table from a subtask dict."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        for col_idx, cdef in enumerate(self.COL_DEFS):
            value = subtask.get(cdef["key"], "")
            self.table.setItem(row, col_idx, QTableWidgetItem(str(value)))

        # Delete button in last column
        btn_del = QPushButton("🗑️")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        name = subtask.get("name", "")
        btn_del.clicked.connect(lambda checked, n=name: self._remove_row_by_name(n))
        self.table.setCellWidget(row, len(self.COL_DEFS), btn_del)

    # ─────────────────── Single add ───────────────────

    def _add_subtask(self):
        """Add a new subtask from the manual input fields."""
        name = self.inp_name.text().strip()
        if not name:
            return

        # Check duplicate
        if any(s['name'] == name for s in self._subtasks):
            QMessageBox.warning(self, "Duplicate", f"'{name}' already exists.")
            return

        priority = self.inp_priority.text().strip()
        est_time = self.inp_time.text().strip()

        subtask = {
            'name': name,
            'priority': priority,
            'est_time': est_time,
            'n_points': '',
            'previous_value': '',
            'perf_brd': '',
        }
        self._subtasks.append(subtask)
        self._add_row(subtask)

        # Clear inputs
        self.inp_name.clear()
        self.inp_priority.clear()
        self.inp_time.clear()
        self.inp_name.setFocus()
        self._update_count()

    # ─────────────────── Bulk Excel import ───────────────────

    def _open_excel_import(self):
        """Open the ExcelImportDialog and bulk-add returned subtasks."""
        from ui.excel_import_dialog import ExcelImportDialog

        dialog = ExcelImportDialog(parent=self)
        if dialog.exec_():
            imported = dialog.get_imported_subtasks()
            if not imported:
                return

            added = 0
            skipped = 0
            for item in imported:
                name = item.get('name', '').strip()
                if not name:
                    continue
                # Skip duplicates
                if any(s['name'] == name for s in self._subtasks):
                    skipped += 1
                    continue

                subtask = {
                    'name': name,
                    'priority': item.get('priority', ''),
                    'est_time': item.get('est_time', ''),
                    'n_points': item.get('n_points', ''),
                    'previous_value': item.get('previous_value', ''),
                    'perf_brd': item.get('perf_brd', ''),
                }
                self._subtasks.append(subtask)
                self._add_row(subtask)
                added += 1

            self._update_count()

            msg = f"✅ Imported {added} subtasks"
            if skipped:
                msg += f" ({skipped} duplicates skipped)"
            QMessageBox.information(self, "Import Complete", msg)
            logger.info(f"Excel import into manual dialog: {added} added, {skipped} skipped")

    # ─────────────────── Remove / Clear ───────────────────

    def _remove_row_by_name(self, name):
        """Remove a subtask by name."""
        self._subtasks = [s for s in self._subtasks if s['name'] != name]
        self._load_subtasks()

    def _clear_all(self):
        """Clear all subtasks."""
        if not self._subtasks:
            return
        reply = QMessageBox.question(self, "Clear All?",
            f"Remove all {len(self._subtasks)} subtasks?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._subtasks = []
            self._load_subtasks()

    # ─────────────────── Count / Getters ───────────────────

    def _update_count(self):
        count = len(self._subtasks)
        self.lbl_count.setText(f"📝 {count} subtask{'s' if count != 1 else ''}")

    def get_subtasks(self):
        """Return the current list of subtasks."""
        return list(self._subtasks)