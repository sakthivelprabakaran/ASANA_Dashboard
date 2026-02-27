"""
Manual Subtask Dialog - Popup for managing ad-hoc test case subtasks.
Provides a spacious table view for adding/removing manual subtasks
with Name, Priority, and Estimated Time fields.
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
    Shows a table with Name, Priority, Est. Time columns.
    Subtasks are edited in-place and returned when dialog is accepted.
    """

    def __init__(self, subtasks=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔧 Manual Subtasks — Ad-Hoc Testing")
        self.setMinimumSize(800, 500)
        self.resize(900, 550)

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

        desc = QLabel("These subtasks will be added to your queue entry without Perf_BRD or Previous values. "
                       "Useful for ad-hoc testing, regression checks, or one-off scenarios.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748b; font-size: 12px; margin-bottom: 4px;")
        layout.addWidget(desc)

        # Input row
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

        # Priority + Time + Add button
        detail_row = QHBoxLayout()
        detail_row.setSpacing(10)

        detail_row.addWidget(QLabel("Priority:"))
        self.inp_priority = QLineEdit()
        self.inp_priority.setPlaceholderText("optional")
        self.inp_priority.setMaximumWidth(120)
        self.inp_priority.setStyleSheet("padding: 6px; border: 1px solid #e2e8f0; border-radius: 4px;")
        detail_row.addWidget(self.inp_priority)

        detail_row.addWidget(QLabel("Est. Time:"))
        self.inp_time = QLineEdit()
        self.inp_time.setPlaceholderText("optional")
        self.inp_time.setMaximumWidth(120)
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

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Subtask Name", "Priority", "Est. Time", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 80)
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

        # Bottom buttons
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

    def _load_subtasks(self):
        """Load subtasks into the table."""
        self.table.setRowCount(0)
        for subtask in self._subtasks:
            self._add_row(subtask['name'], subtask.get('priority', ''), subtask.get('est_time', ''))
        self._update_count()

    def _add_row(self, name, priority='', est_time=''):
        """Add a row to the table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(priority))
        self.table.setItem(row, 2, QTableWidgetItem(est_time))

        # Delete button
        btn_del = QPushButton("🗑️")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        btn_del.clicked.connect(lambda checked, r=row: self._remove_row_by_name(name))
        self.table.setCellWidget(row, 3, btn_del)

    def _add_subtask(self):
        """Add a new subtask from input fields."""
        name = self.inp_name.text().strip()
        if not name:
            return

        # Check duplicate
        if any(s['name'] == name for s in self._subtasks):
            QMessageBox.warning(self, "Duplicate", f"'{name}' already exists.")
            return

        priority = self.inp_priority.text().strip()
        est_time = self.inp_time.text().strip()

        subtask = {'name': name, 'priority': priority, 'est_time': est_time}
        self._subtasks.append(subtask)
        self._add_row(name, priority, est_time)

        # Clear inputs
        self.inp_name.clear()
        self.inp_priority.clear()
        self.inp_time.clear()
        self.inp_name.setFocus()
        self._update_count()

    def _remove_row_by_name(self, name):
        """Remove a subtask by name."""
        self._subtasks = [s for s in self._subtasks if s['name'] != name]
        # Rebuild table
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

    def _update_count(self):
        count = len(self._subtasks)
        self.lbl_count.setText(f"📝 {count} subtask{'s' if count != 1 else ''}")

    def get_subtasks(self):
        """Return the current list of subtasks."""
        return list(self._subtasks)