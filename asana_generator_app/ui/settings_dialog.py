"""
Settings Tab - UI for managing application configuration.
Allows users to add/remove devices, manage CSV fields, display columns,
export headers, and adjust thresholds without editing code.
"""

import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                             QFrame, QScrollArea, QTabWidget, QGroupBox, QDoubleSpinBox,
                             QCheckBox, QSplitter, QInputDialog, QAbstractItemView)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from core.config_manager import ConfigManager

logger = logging.getLogger('AsanaGenerator.Settings')


class ListEditor(QWidget):
    """
    Reusable widget for editing a list of strings.
    Provides Add, Remove, Move Up, Move Down buttons.
    """
    
    def __init__(self, title: str = "", items: list = None, parent=None):
        super().__init__(parent)
        self._title = title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        if title:
            lbl = QLabel(title)
            lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #1e293b;")
            layout.addWidget(lbl)
        
        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #1e293b;
            }
        """)
        layout.addWidget(self.list_widget, 1)
        
        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        
        self.btn_add = QPushButton("➕ Add")
        self.btn_add.clicked.connect(self._add_item)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet("padding: 6px 14px; background: #10b981; color: white; border-radius: 4px; font-weight: bold; font-size: 11px;")
        btn_row.addWidget(self.btn_add)
        
        self.btn_remove = QPushButton("🗑️ Remove")
        self.btn_remove.clicked.connect(self._remove_item)
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.setStyleSheet("padding: 6px 14px; background: #ef4444; color: white; border-radius: 4px; font-weight: bold; font-size: 11px;")
        btn_row.addWidget(self.btn_remove)
        
        self.btn_up = QPushButton("⬆")
        self.btn_up.clicked.connect(self._move_up)
        self.btn_up.setCursor(Qt.PointingHandCursor)
        self.btn_up.setMaximumWidth(40)
        self.btn_up.setStyleSheet("padding: 6px; background: #e2e8f0; border-radius: 4px; font-size: 12px;")
        btn_row.addWidget(self.btn_up)
        
        self.btn_down = QPushButton("⬇")
        self.btn_down.clicked.connect(self._move_down)
        self.btn_down.setCursor(Qt.PointingHandCursor)
        self.btn_down.setMaximumWidth(40)
        self.btn_down.setStyleSheet("padding: 6px; background: #e2e8f0; border-radius: 4px; font-size: 12px;")
        btn_row.addWidget(self.btn_down)
        
        btn_row.addStretch()
        
        self.lbl_count = QLabel(f"0 items")
        self.lbl_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        btn_row.addWidget(self.lbl_count)
        
        layout.addLayout(btn_row)
        
        # Populate if items given
        if items:
            self.set_items(items)
    
    def set_items(self, items: list):
        """Set the list items."""
        self.list_widget.clear()
        for item in items:
            self.list_widget.addItem(str(item))
        self._update_count()
    
    def get_items(self) -> list:
        """Get all items as a list of strings."""
        items = []
        for i in range(self.list_widget.count()):
            items.append(self.list_widget.item(i).text())
        return items
    
    def _add_item(self):
        text, ok = QInputDialog.getText(self, f"Add {self._title}", 
                                         f"Enter new {self._title.lower().rstrip('s')} name:")
        if ok and text.strip():
            # Check for duplicates
            existing = self.get_items()
            if text.strip() in existing:
                QMessageBox.warning(self, "Duplicate", f"'{text.strip()}' already exists.")
                return
            self.list_widget.addItem(text.strip())
            self._update_count()
    
    def _remove_item(self):
        current = self.list_widget.currentRow()
        if current >= 0:
            item = self.list_widget.item(current)
            reply = QMessageBox.question(self, "Remove?",
                f"Remove '{item.text()}'?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.list_widget.takeItem(current)
                self._update_count()
    
    def _move_up(self):
        current = self.list_widget.currentRow()
        if current > 0:
            item = self.list_widget.takeItem(current)
            self.list_widget.insertItem(current - 1, item)
            self.list_widget.setCurrentRow(current - 1)
    
    def _move_down(self):
        current = self.list_widget.currentRow()
        if current < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(current)
            self.list_widget.insertItem(current + 1, item)
            self.list_widget.setCurrentRow(current + 1)
    
    def _update_count(self):
        count = self.list_widget.count()
        self.lbl_count.setText(f"{count} item{'s' if count != 1 else ''}")


class SettingsTab(QWidget):
    """
    Settings tab for managing application configuration.
    Changes are saved to config.json on disk.
    """
    
    def __init__(self, config_manager: ConfigManager = None, parent_window=None):
        super().__init__()
        self.config = config_manager or ConfigManager()
        self.parent_window = parent_window
        self.init_ui()
        self._load_from_config()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f8fafc; }")
        main_layout.addWidget(scroll)
        
        content = QWidget()
        content.setStyleSheet("background: #f8fafc;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(16)
        scroll.setWidget(content)
        
        # Page title
        title = QLabel("⚙️ Application Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1e293b;")
        content_layout.addWidget(title)
        
        subtitle = QLabel("Manage devices, CSV fields, display columns, export headers, and thresholds. "
                          "Changes are saved to config.json — no code edits required.")
        subtitle.setStyleSheet("font-size: 12px; color: #64748b; margin-bottom: 8px;")
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)
        
        # Config file path indicator
        path_label = QLabel(f"📁 Config: {self.config.config_path}")
        path_label.setStyleSheet("font-size: 10px; color: #94a3b8; background: #f1f5f9; "
                                 "padding: 6px 12px; border-radius: 4px;")
        path_label.setWordWrap(True)
        content_layout.addWidget(path_label)
        
        # === INNER TABS for different config sections ===
        self.inner_tabs = QTabWidget()
        self.inner_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #64748b;
                padding: 8px 20px;
                margin-right: 2px;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #7c3aed;
                border-bottom: 2px solid #7c3aed;
            }
            QTabBar::tab:hover {
                background: #e2e8f0;
            }
        """)
        content_layout.addWidget(self.inner_tabs, 1)
        
        # --- Tab 1: Devices ---
        devices_tab = QWidget()
        devices_layout = QVBoxLayout(devices_tab)
        devices_layout.setContentsMargins(16, 16, 16, 16)
        
        devices_info = QLabel(
            "📱 <b>Devices</b> — These appear in the Task Creator's device dropdown. "
            "Add new devices here when your team starts testing on new hardware."
        )
        devices_info.setWordWrap(True)
        devices_info.setStyleSheet("color: #475569; font-size: 12px; background: #f5f3ff; "
                                   "padding: 10px; border-radius: 6px; border-left: 3px solid #7c3aed;")
        devices_layout.addWidget(devices_info)
        
        self.devices_editor = ListEditor("Devices")
        devices_layout.addWidget(self.devices_editor, 1)
        
        self.inner_tabs.addTab(devices_tab, "📱 Devices")
        
        # --- Tab 2: CSV Fields ---
        fields_tab = QWidget()
        fields_layout = QVBoxLayout(fields_tab)
        fields_layout.setContentsMargins(16, 16, 16, 16)
        
        fields_info = QLabel(
            "📋 <b>CSV Fields</b> — These are the Asana CSV column names the app recognizes. "
            "When new custom fields are added to your Asana project, add them to the appropriate category here."
        )
        fields_info.setWordWrap(True)
        fields_info.setStyleSheet("color: #475569; font-size: 12px; background: #ecfdf5; "
                                   "padding: 10px; border-radius: 6px; border-left: 3px solid #10b981;")
        fields_layout.addWidget(fields_info)
        
        # Sub-tabs for field categories
        self.fields_tabs = QTabWidget()
        self.fields_tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 6px 14px; font-size: 11px;
                background: #f8fafc; border: 1px solid #e2e8f0;
                border-bottom: none; border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected { background: #ffffff; font-weight: bold; }
        """)
        fields_layout.addWidget(self.fields_tabs, 1)
        
        self.field_editors = {}
        field_categories = [
            ("core_fields", "Core Fields", "Name, Section, Parent task, Projects, Devices"),
            ("performance_fields", "Performance", "Average, Perf_BRD, Previous Value"),
            ("status_fields", "Status", "Priority, BRD Status, Previous Status"),
            ("deviation_fields", "Deviation", "Deviation % columns"),
            ("iteration_fields", "Iterations", "Iteration_01 through Iteration_10+"),
            ("meta_fields", "Meta Fields", "GREEN, YELLOW, RED, Assignee, etc."),
        ]
        
        for cat_key, cat_label, cat_desc in field_categories:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(8, 8, 8, 8)
            
            desc = QLabel(f"<i>{cat_desc}</i>")
            desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
            tab_layout.addWidget(desc)
            
            editor = ListEditor(cat_label)
            self.field_editors[cat_key] = editor
            tab_layout.addWidget(editor, 1)
            
            self.fields_tabs.addTab(tab_widget, cat_label)
        
        self.inner_tabs.addTab(fields_tab, "📋 CSV Fields")
        
        # --- Tab 3: Display Columns ---
        display_tab = QWidget()
        display_layout = QVBoxLayout(display_tab)
        display_layout.setContentsMargins(16, 16, 16, 16)
        
        display_info = QLabel(
            "📊 <b>Display Columns</b> — These columns appear in the Report Generator table. "
            "Toggle visibility, reorder, or add new columns. Key = CSV field name, Label = display name."
        )
        display_info.setWordWrap(True)
        display_info.setStyleSheet("color: #475569; font-size: 12px; background: #fef3c7; "
                                   "padding: 10px; border-radius: 6px; border-left: 3px solid #f59e0b;")
        display_layout.addWidget(display_info)
        
        # Display columns list with checkboxes
        self.display_list = QListWidget()
        self.display_list.setAlternatingRowColors(True)
        self.display_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.display_list.setStyleSheet("""
            QListWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #f1f5f9; }
            QListWidget::item:selected { background: #eff6ff; }
        """)
        display_layout.addWidget(self.display_list, 1)
        
        # Display column buttons
        dcol_btn_row = QHBoxLayout()
        dcol_btn_row.setSpacing(8)
        
        btn_add_dcol = QPushButton("➕ Add Column")
        btn_add_dcol.clicked.connect(self._add_display_column)
        btn_add_dcol.setCursor(Qt.PointingHandCursor)
        btn_add_dcol.setStyleSheet("padding: 6px 14px; background: #10b981; color: white; border-radius: 4px; font-weight: bold; font-size: 11px;")
        dcol_btn_row.addWidget(btn_add_dcol)
        
        btn_remove_dcol = QPushButton("🗑️ Remove")
        btn_remove_dcol.clicked.connect(self._remove_display_column)
        btn_remove_dcol.setCursor(Qt.PointingHandCursor)
        btn_remove_dcol.setStyleSheet("padding: 6px 14px; background: #ef4444; color: white; border-radius: 4px; font-weight: bold; font-size: 11px;")
        dcol_btn_row.addWidget(btn_remove_dcol)
        
        dcol_btn_row.addStretch()
        display_layout.addLayout(dcol_btn_row)
        
        self.inner_tabs.addTab(display_tab, "📊 Display Columns")
        
        # --- Tab 4: Export Headers ---
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        export_layout.setContentsMargins(16, 16, 16, 16)
        
        export_info = QLabel(
            "💾 <b>Export Headers</b> — These are the column headers written to the CSV file when exporting. "
            "Must match Asana's expected CSV format for import."
        )
        export_info.setWordWrap(True)
        export_info.setStyleSheet("color: #475569; font-size: 12px; background: #fee2e2; "
                                   "padding: 10px; border-radius: 6px; border-left: 3px solid #ef4444;")
        export_layout.addWidget(export_info)
        
        self.export_editor = ListEditor("Export Headers")
        export_layout.addWidget(self.export_editor, 1)
        
        self.inner_tabs.addTab(export_tab, "💾 Export Headers")
        
        # --- Tab 5: Thresholds ---
        thresh_tab = QWidget()
        thresh_layout = QVBoxLayout(thresh_tab)
        thresh_layout.setContentsMargins(16, 16, 16, 16)
        
        thresh_info = QLabel(
            "🎯 <b>Thresholds</b> — Control the deviation percentage thresholds for GREEN/YELLOW/RED classification. "
            "These affect how PASS/FAIL is determined in the Report Generator."
        )
        thresh_info.setWordWrap(True)
        thresh_info.setStyleSheet("color: #475569; font-size: 12px; background: #ecfdf5; "
                                   "padding: 10px; border-radius: 6px; border-left: 3px solid #10b981;")
        thresh_layout.addWidget(thresh_info)
        
        # Threshold editors
        thresh_frame = QFrame()
        thresh_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;")
        thresh_form = QVBoxLayout(thresh_frame)
        thresh_form.setContentsMargins(20, 16, 20, 16)
        thresh_form.setSpacing(16)
        
        # GREEN threshold
        green_row = QHBoxLayout()
        green_label = QLabel("🟢 GREEN max deviation:")
        green_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        green_row.addWidget(green_label)
        green_row.addStretch()
        self.spin_green = QDoubleSpinBox()
        self.spin_green.setRange(0.0, 1.0)
        self.spin_green.setSingleStep(0.001)
        self.spin_green.setDecimals(4)
        self.spin_green.setSuffix("  (fraction)")
        self.spin_green.setMinimumWidth(180)
        self.spin_green.setStyleSheet("padding: 6px; font-size: 13px;")
        green_row.addWidget(self.spin_green)
        self.lbl_green_pct = QLabel("")
        self.lbl_green_pct.setStyleSheet("color: #10b981; font-weight: bold; font-size: 13px; min-width: 60px;")
        green_row.addWidget(self.lbl_green_pct)
        thresh_form.addLayout(green_row)
        
        green_desc = QLabel("Deviations below this value are classified as GREEN (negligible). Default: 0.005 = 0.5%")
        green_desc.setStyleSheet("color: #94a3b8; font-size: 11px; margin-left: 20px;")
        thresh_form.addWidget(green_desc)
        
        # YELLOW threshold (also PASS/FAIL boundary)
        yellow_row = QHBoxLayout()
        yellow_label = QLabel("🟡 YELLOW max (PASS/FAIL boundary):")
        yellow_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        yellow_row.addWidget(yellow_label)
        yellow_row.addStretch()
        self.spin_yellow = QDoubleSpinBox()
        self.spin_yellow.setRange(0.0, 1.0)
        self.spin_yellow.setSingleStep(0.01)
        self.spin_yellow.setDecimals(4)
        self.spin_yellow.setSuffix("  (fraction)")
        self.spin_yellow.setMinimumWidth(180)
        self.spin_yellow.setStyleSheet("padding: 6px; font-size: 13px;")
        yellow_row.addWidget(self.spin_yellow)
        self.lbl_yellow_pct = QLabel("")
        self.lbl_yellow_pct.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 13px; min-width: 60px;")
        yellow_row.addWidget(self.lbl_yellow_pct)
        thresh_form.addLayout(yellow_row)
        
        yellow_desc = QLabel("Deviations below this are PASS (GREEN or YELLOW). Above = RED / FAIL. Default: 0.10 = 10%")
        yellow_desc.setStyleSheet("color: #94a3b8; font-size: 11px; margin-left: 20px;")
        thresh_form.addWidget(yellow_desc)
        
        thresh_layout.addWidget(thresh_frame)
        
        # Update percentage labels when spinboxes change
        self.spin_green.valueChanged.connect(
            lambda v: self.lbl_green_pct.setText(f"= {v * 100:.2f}%"))
        self.spin_yellow.valueChanged.connect(
            lambda v: self.lbl_yellow_pct.setText(f"= {v * 100:.2f}%"))
        
        # Default export values
        defaults_frame = QFrame()
        defaults_frame.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 8px;")
        defaults_form = QVBoxLayout(defaults_frame)
        defaults_form.setContentsMargins(20, 16, 20, 16)
        defaults_form.setSpacing(10)
        
        defaults_title = QLabel("📝 Default Export Values")
        defaults_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b;")
        defaults_form.addWidget(defaults_title)
        
        defaults_desc = QLabel("These values are pre-filled in exported CSV rows for threshold columns.")
        defaults_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        defaults_form.addWidget(defaults_desc)
        
        self.default_value_inputs = {}
        for label_name in ['GREEN', 'YELLOW', 'RED']:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label_name}:"))
            inp = QLineEdit()
            inp.setMaximumWidth(100)
            inp.setStyleSheet("padding: 4px 8px; font-size: 12px;")
            self.default_value_inputs[label_name] = inp
            row.addWidget(inp)
            row.addStretch()
            defaults_form.addLayout(row)
        
        thresh_layout.addWidget(defaults_frame)
        thresh_layout.addStretch()
        
        self.inner_tabs.addTab(thresh_tab, "🎯 Thresholds")
        
        # --- Tab 6: Assignees ---
        assignee_tab = QWidget()
        assignee_layout = QVBoxLayout(assignee_tab)
        assignee_layout.setContentsMargins(16, 16, 16, 16)
        
        assignee_info = QLabel(
            "👤 <b>Assignees</b> — Team members who can be assigned to tasks. "
            "The dropdown in Task Creator shows the Name, while the exported CSV uses the Email. "
            "Add or remove team members as your team changes."
        )
        assignee_info.setWordWrap(True)
        assignee_info.setStyleSheet("color: #475569; font-size: 12px; background: #eff6ff; "
                                    "padding: 10px; border-radius: 6px; border-left: 3px solid #3b82f6;")
        assignee_layout.addWidget(assignee_info)
        
        # Assignee list
        self.assignee_list = QListWidget()
        self.assignee_list.setAlternatingRowColors(True)
        self.assignee_list.setStyleSheet("""
            QListWidget { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px; font-size: 12px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #f1f5f9; }
            QListWidget::item:selected { background: #eff6ff; }
        """)
        assignee_layout.addWidget(self.assignee_list, 1)
        
        # Assignee buttons
        asgn_btn_row = QHBoxLayout()
        asgn_btn_row.setSpacing(8)
        
        btn_add_assignee = QPushButton("➕ Add Assignee")
        btn_add_assignee.clicked.connect(self._add_assignee)
        btn_add_assignee.setCursor(Qt.PointingHandCursor)
        btn_add_assignee.setStyleSheet("padding: 6px 14px; background: #10b981; color: white; border-radius: 4px; font-weight: bold; font-size: 11px;")
        asgn_btn_row.addWidget(btn_add_assignee)
        
        btn_remove_assignee = QPushButton("🗑️ Remove")
        btn_remove_assignee.clicked.connect(self._remove_assignee)
        btn_remove_assignee.setCursor(Qt.PointingHandCursor)
        btn_remove_assignee.setStyleSheet("padding: 6px 14px; background: #ef4444; color: white; border-radius: 4px; font-weight: bold; font-size: 11px;")
        asgn_btn_row.addWidget(btn_remove_assignee)
        
        asgn_btn_row.addStretch()
        
        self.lbl_assignee_count = QLabel("0 assignees")
        self.lbl_assignee_count.setStyleSheet("color: #94a3b8; font-size: 11px;")
        asgn_btn_row.addWidget(self.lbl_assignee_count)
        
        assignee_layout.addLayout(asgn_btn_row)
        
        self.inner_tabs.addTab(assignee_tab, "👤 Assignees")
        
        # === SAVE BAR (always visible at bottom) ===
        save_bar = QFrame()
        save_bar.setStyleSheet("background: #ffffff; border-top: 1px solid #e2e8f0;")
        save_bar.setFixedHeight(56)
        save_layout = QHBoxLayout(save_bar)
        save_layout.setContentsMargins(24, 8, 24, 8)
        
        self.lbl_save_status = QLabel("")
        self.lbl_save_status.setStyleSheet("color: #64748b; font-size: 12px;")
        save_layout.addWidget(self.lbl_save_status)
        
        save_layout.addStretch()
        
        btn_reload = QPushButton("↻ Reload from File")
        btn_reload.clicked.connect(self._reload_config)
        btn_reload.setCursor(Qt.PointingHandCursor)
        btn_reload.setStyleSheet("""
            QPushButton {
                padding: 8px 20px; background: #f1f5f9; color: #475569;
                border: 1px solid #e2e8f0; border-radius: 6px;
                font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        save_layout.addWidget(btn_reload)
        
        btn_save = QPushButton("💾 Save Changes")
        btn_save.clicked.connect(self._save_config)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                padding: 8px 24px; background: #10b981; color: white;
                border: none; border-radius: 6px;
                font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #059669; }
        """)
        save_layout.addWidget(btn_save)
        
        main_layout.addWidget(save_bar)
    
    # ====================
    # LOAD / SAVE
    # ====================
    
    def _load_from_config(self):
        """Load all settings from ConfigManager into the UI."""
        # Devices
        self.devices_editor.set_items(self.config.get_devices())
        
        # Assignees
        self._load_assignees()
        
        # CSV Fields by category
        for cat_key, editor in self.field_editors.items():
            editor.set_items(self.config.get_csv_fields_by_category(cat_key))
        
        # Display columns (with checkboxes for visibility)
        self._load_display_columns()
        
        # Export headers
        self.export_editor.set_items(self.config.get_export_headers())
        
        # Thresholds
        thresholds = self.config.get_thresholds()
        self.spin_green.setValue(thresholds.get('green_max_deviation', 0.005))
        self.spin_yellow.setValue(thresholds.get('yellow_max_deviation', 0.10))
        
        # Default export values
        defaults = self.config.get_default_export_values()
        for key, inp in self.default_value_inputs.items():
            inp.setText(defaults.get(key, ''))
        
        self.lbl_save_status.setText("Loaded from config.json")
    
    def _load_display_columns(self):
        """Load display columns into the list with checkboxes."""
        self.display_list.clear()
        columns = self.config.get_display_columns(visible_only=False)
        
        for col in columns:
            key = col.get('key', '')
            label = col.get('label', key)
            visible = col.get('visible', True)
            
            item = QListWidgetItem(f"{key}  →  {label}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if visible else Qt.Unchecked)
            item.setData(Qt.UserRole, col)  # Store full dict
            self.display_list.addItem(item)
    
    def _save_config(self):
        """Save all UI state back to ConfigManager and disk."""
        try:
            # Devices
            self.config.set_devices(self.devices_editor.get_items())
            
            # CSV Fields
            csv_fields = {}
            for cat_key, editor in self.field_editors.items():
                csv_fields[cat_key] = editor.get_items()
            self.config._config['csv_fields'] = csv_fields
            
            # Display columns
            columns = []
            for i in range(self.display_list.count()):
                item = self.display_list.item(i)
                col_data = item.data(Qt.UserRole)
                if col_data:
                    col_data['visible'] = (item.checkState() == Qt.Checked)
                    columns.append(col_data)
            self.config.set_display_columns(columns)
            
            # Export headers
            self.config.set_export_headers(self.export_editor.get_items())
            
            # Thresholds
            self.config.set_thresholds(
                self.spin_green.value(),
                self.spin_yellow.value()
            )
            
            # Default export values
            defaults = {}
            for key, inp in self.default_value_inputs.items():
                defaults[key] = inp.text().strip()
            self.config._config['default_export_values'] = defaults
            
            # Assignees
            assignees = []
            for i in range(self.assignee_list.count()):
                item = self.assignee_list.item(i)
                data = item.data(Qt.UserRole)
                if data:
                    assignees.append(data)
            self.config.set_assignees(assignees)
            
            # Save to disk
            if self.config.save():
                self.lbl_save_status.setText("✅ Saved successfully!")
                self.lbl_save_status.setStyleSheet("color: #10b981; font-size: 12px; font-weight: bold;")
                
                # Refresh device dropdown in parent window if available
                if self.parent_window and hasattr(self.parent_window, 'combo_device'):
                    current_device = self.parent_window.combo_device.currentText()
                    self.parent_window.combo_device.clear()
                    self.parent_window.combo_device.addItems(self.config.get_devices())
                    # Restore selection if still valid
                    idx = self.parent_window.combo_device.findText(current_device)
                    if idx >= 0:
                        self.parent_window.combo_device.setCurrentIndex(idx)
                
                # Refresh assignee dropdown in parent window
                if self.parent_window and hasattr(self.parent_window, '_populate_assignee_dropdown'):
                    self.parent_window._populate_assignee_dropdown()
                
                logger.info("Settings saved to config.json")
                
                QMessageBox.information(self, "Saved", 
                    "Settings saved successfully!\n\n"
                    "Note: Some changes (like display columns) will take effect "
                    "after re-importing data or restarting the app.")
            else:
                self.lbl_save_status.setText("❌ Save failed!")
                self.lbl_save_status.setStyleSheet("color: #ef4444; font-size: 12px; font-weight: bold;")
                
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save settings:\n{str(e)}")
            self.lbl_save_status.setText(f"❌ Error: {str(e)}")
            self.lbl_save_status.setStyleSheet("color: #ef4444; font-size: 12px;")
    
    def _reload_config(self):
        """Reload config from disk and refresh UI."""
        self.config.reload()
        self._load_from_config()
        self.lbl_save_status.setText("↻ Reloaded from config.json")
        self.lbl_save_status.setStyleSheet("color: #3b82f6; font-size: 12px; font-weight: bold;")
    
    # ====================
    # DISPLAY COLUMN MANAGEMENT
    # ====================
    
    def _add_display_column(self):
        """Add a new display column (prompts for key and label)."""
        key, ok1 = QInputDialog.getText(self, "Add Display Column",
            "Enter the CSV field name (key):\n"
            "e.g., 'Iteration_01' or 'New_Field'")
        if not ok1 or not key.strip():
            return
        
        label, ok2 = QInputDialog.getText(self, "Column Label",
            f"Enter the display label for '{key.strip()}':\n"
            "e.g., 'Iter 01' or 'New Field'",
            QLineEdit.Normal, key.strip())
        if not ok2 or not label.strip():
            return
        
        key = key.strip()
        label = label.strip()
        
        # Check for duplicate keys
        for i in range(self.display_list.count()):
            existing = self.display_list.item(i).data(Qt.UserRole)
            if existing and existing.get('key') == key:
                QMessageBox.warning(self, "Duplicate", f"Column '{key}' already exists.")
                return
        
        col_data = {"key": key, "label": label, "visible": True}
        item = QListWidgetItem(f"{key}  →  {label}")
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setData(Qt.UserRole, col_data)
        self.display_list.addItem(item)
    
    # ====================
    # ASSIGNEE MANAGEMENT
    # ====================
    
    def _load_assignees(self):
        """Load assignees into the list widget."""
        self.assignee_list.clear()
        for assignee in self.config.get_assignees():
            name = assignee.get('name', '')
            email = assignee.get('email', '')
            item = QListWidgetItem(f"👤 {name}  —  {email}")
            item.setData(Qt.UserRole, assignee)
            self.assignee_list.addItem(item)
        self.lbl_assignee_count.setText(f"{self.assignee_list.count()} assignee(s)")
    
    def _add_assignee(self):
        """Add a new assignee (prompts for name and email)."""
        name, ok1 = QInputDialog.getText(self, "Add Assignee",
            "Enter the assignee's display name:\ne.g., 'John Doe'")
        if not ok1 or not name.strip():
            return
        
        email, ok2 = QInputDialog.getText(self, "Assignee Email",
            f"Enter the email for '{name.strip()}':\ne.g., 'john.doe@amazon.com'",
            QLineEdit.Normal, "")
        if not ok2 or not email.strip():
            return
        
        name = name.strip()
        email = email.strip()
        
        # Check for duplicate email
        for i in range(self.assignee_list.count()):
            existing = self.assignee_list.item(i).data(Qt.UserRole)
            if existing and existing.get('email', '').lower() == email.lower():
                QMessageBox.warning(self, "Duplicate", f"Email '{email}' already exists.")
                return
        
        assignee = {"name": name, "email": email}
        item = QListWidgetItem(f"👤 {name}  —  {email}")
        item.setData(Qt.UserRole, assignee)
        self.assignee_list.addItem(item)
        self.lbl_assignee_count.setText(f"{self.assignee_list.count()} assignee(s)")
    
    def _remove_assignee(self):
        """Remove the selected assignee."""
        current = self.assignee_list.currentRow()
        if current >= 0:
            item = self.assignee_list.item(current)
            data = item.data(Qt.UserRole)
            name = data.get('name', '') if data else item.text()
            
            reply = QMessageBox.question(self, "Remove Assignee?",
                f"Remove assignee '{name}'?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.assignee_list.takeItem(current)
                self.lbl_assignee_count.setText(f"{self.assignee_list.count()} assignee(s)")
    
    def _remove_display_column(self):
        """Remove the selected display column."""
        current = self.display_list.currentRow()
        if current >= 0:
            item = self.display_list.item(current)
            col_data = item.data(Qt.UserRole)
            name = col_data.get('key', '') if col_data else item.text()
            
            reply = QMessageBox.question(self, "Remove Column?",
                f"Remove display column '{name}'?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.display_list.takeItem(current)
