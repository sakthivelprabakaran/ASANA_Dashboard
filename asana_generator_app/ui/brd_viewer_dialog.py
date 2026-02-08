"""
BRD Spreadsheet Viewer Dialog
A modal dialog matching the web app's spreadsheet viewer functionality:
- Shows ALL BRD data (scrollable)
- Real-time column search with multi-keyword support
- Quick filter buttons for common device searches
- Visual column selection for Perf/Prev columns (green/orange highlighting)
- Match count and navigation
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QLineEdit, QPushButton, QLabel,
                             QWidget, QHeaderView, QAbstractItemView, QFrame,
                             QSizePolicy, QStyledItemDelegate, QStyleOptionViewItem)
from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtGui import QColor, QBrush, QFont, QPainter
from typing import List, Any, Dict


class ColumnHighlightDelegate(QStyledItemDelegate):
    """Custom delegate to paint column backgrounds for highlighting."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.perf_col = -1
        self.prev_col = -1
        self.match_cols = []
        
        # Bright test colors
        self.COLOR_PERF = QColor(0, 255, 0)      # Bright green
        self.COLOR_PREV = QColor(255, 255, 0)    # Bright yellow  
        self.COLOR_MATCH = QColor(0, 255, 255)   # Bright cyan
        self.COLOR_EVEN = QColor(255, 255, 255)  # White
        self.COLOR_ODD = QColor(248, 250, 252)   # Light gray
    
    def set_highlighting(self, perf_col: int, prev_col: int, match_cols: List[int]):
        """Update which columns should be highlighted."""
        self.perf_col = perf_col
        self.prev_col = prev_col
        self.match_cols = match_cols
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        """Custom paint to draw background colors."""
        # Get the column (subtract 1 for row number column)
        table_col = index.column()
        adjusted_col = table_col - 1 if table_col > 0 else -1
        row = index.row()
        
        # Determine background color
        if adjusted_col == self.perf_col:
            bg_color = self.COLOR_PERF
        elif adjusted_col == self.prev_col:
            bg_color = self.COLOR_PREV
        elif adjusted_col in self.match_cols:
            bg_color = self.COLOR_MATCH
        else:
            # Alternating row colors
            bg_color = self.COLOR_ODD if row % 2 == 1 else self.COLOR_EVEN
        
        # Fill background
        painter.fillRect(option.rect, bg_color)
        
        # Draw the text on top
        super().paint(painter, option, index)



class BrdViewerDialog(QDialog):
    """
    Dialog for viewing BRD spreadsheet data and selecting columns.
    Matches web app's spreadsheet viewer UX.
    """
    
    # Solid colors without alpha for maximum visibility
    COLOR_PERF = QColor(134, 239, 172)    # Light green (#86efac) - fully opaque
    COLOR_PREV = QColor(253, 186, 116)    # Light orange (#fdba74) - fully opaque
    COLOR_MATCH = QColor(147, 197, 253)   # Light blue (#93c5fd) - fully opaque
    COLOR_HEADER = QColor(241, 245, 249)
    
    def __init__(self, brd_data: List[List[Any]], parent=None, initial_search: str = ""):
        super().__init__(parent)
        self.brd_data = brd_data
        self.initial_search = initial_search  # Device name for auto-search
        
        # Use first row as headers (fallback to indexes)
        self.headers = []
        if brd_data:
            self.headers = [str(h) if h and str(h).lower() != 'nan' else f"Col {i}" 
                          for i, h in enumerate(brd_data[0])]
        
        # All data rows (skip header row)
        self.data_rows = brd_data[1:] if len(brd_data) > 1 else []
        
        # Selection state
        self.selected_perf_col = {"name": "", "index": -1}
        self.selected_prev_col = {"name": "", "index": -1}
        self.selection_mode = "perf"  # 'perf' or 'prev'
        self.current_matches = []
        
        self.init_ui()
        self.apply_styles()
        
        # Auto-search with device name if provided
        if self.initial_search:
            self.search_input.setText(self.initial_search)
            self.search_columns(self.initial_search)
        
    def init_ui(self):
        self.setWindowTitle("📊 BRD Column Selection - Click Column Headers to Select")
        self.setMinimumSize(1300, 800)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # === INSTRUCTIONS ===
        instr = QLabel("💡 Tip: Search for your device (e.g., 'Malbec') then click the column header to select")
        instr.setStyleSheet("color: #475569; font-size: 13px; padding: 8px; background: #f1f5f9; border-radius: 6px; border: 1px solid #e2e8f0;")
        layout.addWidget(instr)
        
        # === SEARCH BAR ===
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(10)
        
        search_label = QLabel("🔍 Search:")
        search_label.setStyleSheet("color: #1e293b; font-weight: bold;")
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search columns... (e.g., 'Malbec BRD' or 'Previous Value')")
        self.search_input.textChanged.connect(self.search_columns)
        self.search_input.setMinimumHeight(40)
        search_layout.addWidget(self.search_input, 1)
        
        # Match info
        self.match_info = QLabel("")
        self.match_info.setMinimumWidth(150)
        search_layout.addWidget(self.match_info)
        
        layout.addWidget(search_widget)
        
        # === QUICK FILTERS ===
        filters_widget = QWidget()
        filters_layout = QHBoxLayout(filters_widget)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(8)
        
        filters_label = QLabel("Quick Filters:")
        filters_label.setStyleSheet("color: #94a3b8;")
        filters_layout.addWidget(filters_label)
        
        # Device filters (matching web app device list)
        quick_filters = ["Malbec", "Cava", "Barolo", "Rossini", "Sangria", "Pisco", 
                        "Previous", "BRD", "Deviation"]
        for filter_text in quick_filters:
            btn = QPushButton(filter_text)
            btn.setObjectName("quickFilter")
            btn.clicked.connect(lambda checked, t=filter_text: self.quick_search(t))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMaximumWidth(100)
            filters_layout.addWidget(btn)
        
        filters_layout.addStretch()
        layout.addWidget(filters_widget)
        
        # === MODE SELECTION ===
        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(15)
        
        mode_label = QLabel("Select Column Type:")
        mode_label.setStyleSheet("color: #1e293b; font-weight: bold;")
        mode_layout.addWidget(mode_label)
        
        self.btn_mode_perf = QPushButton("🎯 Performance/BRD Column (Green)")
        self.btn_mode_perf.setObjectName("modePerf")
        self.btn_mode_perf.setCheckable(True)
        self.btn_mode_perf.setChecked(True)
        self.btn_mode_perf.clicked.connect(lambda: self.set_selection_mode("perf"))
        self.btn_mode_perf.setCursor(Qt.PointingHandCursor)
        mode_layout.addWidget(self.btn_mode_perf)
        
        self.btn_mode_prev = QPushButton("📊 Previous Value Column (Orange)")
        self.btn_mode_prev.setObjectName("modePrev")
        self.btn_mode_prev.setCheckable(True)
        self.btn_mode_prev.clicked.connect(lambda: self.set_selection_mode("prev"))
        self.btn_mode_prev.setCursor(Qt.PointingHandCursor)
        mode_layout.addWidget(self.btn_mode_prev)
        
        mode_layout.addStretch()
        
        # Row count info
        row_count = QLabel(f"📋 {len(self.data_rows)} data rows × {len(self.headers)} columns")
        row_count.setStyleSheet("color: #64748b; font-size: 13px;")
        mode_layout.addWidget(row_count)
        
        layout.addWidget(mode_widget)
        
        # === DATA TABLE ===
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers) + 1)  # +1 for row numbers
        self.table.setRowCount(min(len(self.data_rows), 500))  # Show up to 500 rows
        
        # Install custom delegate for column highlighting
        self.delegate = ColumnHighlightDelegate(self.table)
        self.table.setItemDelegate(self.delegate)
        
        # Set headers
        header_labels = ["#"] + [self._truncate(str(h), 40) for h in self.headers]
        self.table.setHorizontalHeaderLabels(header_labels)
        
        # Configure table
        self.table.setAlternatingRowColors(False)  # Delegate handles backgrounds
        self.table.setSelectionMode(QAbstractItemView.NoSelection)  # Disable cell selection
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.horizontalHeader().setDefaultSectionSize(120)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table.verticalHeader().setVisible(False)
        
        # Make header clickable and styled
        header = self.table.horizontalHeader()
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #475569;
                padding: 8px 4px;
                border: 1px solid #e2e8f0;
                font-weight: bold;
                font-size: 11px;
            }
            QHeaderView::section:hover {
                background-color: #e2e8f0;
                color: #1e40af;
            }
        """)
        
        # Colors for alternating rows
        bg_even = QColor(255, 255, 255)  # White
        bg_odd = QColor(248, 250, 252)   # Light gray (#f8fafc)
        
        # Populate data - handle empty cells properly
        for row_idx, row_data in enumerate(self.data_rows[:500]):
            # Determine row background
            row_bg = bg_odd if row_idx % 2 == 1 else bg_even
            
            # Row number
            num_item = QTableWidgetItem(str(row_idx + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setForeground(QBrush(QColor("#64748b")))
            num_item.setBackground(QBrush(row_bg))
            self.table.setItem(row_idx, 0, num_item)
            
            # Data cells
            for col_idx in range(len(self.headers)):
                cell_value = row_data[col_idx] if col_idx < len(row_data) else ""
                
                # Convert to string and handle empty/nan values
                display_value = str(cell_value) if cell_value else ""
                if display_value.lower() in ['nan', 'none', 'null']:
                    display_value = ""
                
                item = QTableWidgetItem(self._truncate(display_value, 50))
                item.setToolTip(str(cell_value) if cell_value else "Empty")
                item.setBackground(QBrush(row_bg))  # Set initial background
                
                # Style empty cells differently
                if not display_value:
                    item.setForeground(QBrush(QColor("#64748b")))
                    item.setText("—")  # Em dash for empty
                    
                self.table.setItem(row_idx, col_idx + 1, item)
        
        layout.addWidget(self.table, 1)
        
        # === SELECTED COLUMNS DISPLAY ===
        selection_widget = QWidget()
        selection_widget.setStyleSheet("background-color: #f8fafc; border-radius: 8px; padding: 15px; border: 1px solid #e2e8f0;")
        selection_layout = QHBoxLayout(selection_widget)
        selection_layout.setSpacing(20)
        
        # Perf selection box
        perf_box = QFrame()
        perf_box.setStyleSheet("""
            QFrame {
                background-color: #ecfdf5; 
                border: 2px solid #10b981; 
                border-radius: 8px;
            }
        """)
        perf_layout = QVBoxLayout(perf_box)
        perf_layout.setContentsMargins(15, 12, 15, 12)
        
        perf_title = QLabel("✓ Perf/BRD Column:")
        perf_title.setStyleSheet("color: #059669; font-weight: bold;")
        perf_layout.addWidget(perf_title)
        
        self.lbl_selected_perf = QLabel("Click a column header to select")
        self.lbl_selected_perf.setStyleSheet("color: #047857; font-size: 14px;")
        self.lbl_selected_perf.setWordWrap(True)
        perf_layout.addWidget(self.lbl_selected_perf)
        
        selection_layout.addWidget(perf_box, 1)
        
        # Prev selection box
        prev_box = QFrame()
        prev_box.setStyleSheet("""
            QFrame {
                background-color: #fef3c7; 
                border: 2px solid #f59e0b; 
                border-radius: 8px;
            }
        """)
        prev_layout = QVBoxLayout(prev_box)
        prev_layout.setContentsMargins(15, 12, 15, 12)
        
        prev_title = QLabel("✓ Previous Value Column:")
        prev_title.setStyleSheet("color: #b45309; font-weight: bold;")
        prev_layout.addWidget(prev_title)
        
        self.lbl_selected_prev = QLabel("Click a column header to select")
        self.lbl_selected_prev.setStyleSheet("color: #92400e; font-size: 14px;")
        self.lbl_selected_prev.setWordWrap(True)
        prev_layout.addWidget(self.lbl_selected_prev)
        
        selection_layout.addWidget(prev_box, 1)
        
        # Action buttons
        btn_box = QVBoxLayout()
        btn_box.setSpacing(10)
        
        self.btn_confirm = QPushButton("✓ Confirm & Close")
        self.btn_confirm.setObjectName("success")
        self.btn_confirm.clicked.connect(self.accept)
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setMinimumHeight(45)
        self.btn_confirm.setMinimumWidth(160)
        btn_box.addWidget(self.btn_confirm)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_box.addWidget(btn_cancel)
        
        selection_layout.addLayout(btn_box)
        
        layout.addWidget(selection_widget)
        
    def _truncate(self, text: str, length: int) -> str:
        """Truncate text with ellipsis."""
        return text[:length] + "…" if len(text) > length else text
        
    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #1e293b;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                color: #1e293b;
                padding: 10px 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
            QPushButton#quickFilter {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                color: #475569;
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton#quickFilter:hover {
                background-color: #e2e8f0;
                border-color: #3b82f6;
                color: #1e40af;
            }
            QPushButton#modePerf, QPushButton#modePrev {
                background-color: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                color: #475569;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton#modePerf:checked {
                background-color: #ecfdf5;
                border-color: #10b981;
                color: #059669;
            }
            QPushButton#modePrev:checked {
                background-color: #fef3c7;
                border-color: #f59e0b;
                color: #b45309;
            }
            QPushButton#success {
                background-color: #10b981;
                border: none;
                border-radius: 8px;
                color: white;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#success:hover {
                background-color: #059669;
            }
            QPushButton#secondary {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                color: #475569;
                padding: 10px 20px;
            }
            QPushButton#secondary:hover {
                background-color: #e2e8f0;
            }
            QLabel {
                color: #64748b;
            }
        """)
        
    def set_selection_mode(self, mode: str):
        """Switch between Perf and Prev column selection mode."""
        self.selection_mode = mode
        self.btn_mode_perf.setChecked(mode == "perf")
        self.btn_mode_prev.setChecked(mode == "prev")
        
    def on_header_clicked(self, logical_index: int):
        """Handle column header click for selection."""
        if logical_index == 0:  # Skip row number column
            return
            
        col_index = logical_index - 1
        col_name = self.headers[col_index] if col_index < len(self.headers) else f"Column {col_index}"
        
        if self.selection_mode == "perf":
            self.selected_perf_col = {"name": col_name, "index": col_index}
            self.lbl_selected_perf.setText(f"✓ {col_name}")
            # Auto-switch to prev mode after selecting perf
            self.set_selection_mode("prev")
        else:
            self.selected_prev_col = {"name": col_name, "index": col_index}
            self.lbl_selected_prev.setText(f"✓ {col_name}")
            
        self.update_column_highlighting()
        
    def update_column_highlighting(self):
        """Update visual highlighting of selected and matched columns using delegate."""
        perf_idx = self.selected_perf_col.get("index", -1)
        prev_idx = self.selected_prev_col.get("index", -1)
        
        # DEBUG
        print(f"DEBUG: update_column_highlighting called")
        print(f"DEBUG: perf_idx={perf_idx}, prev_idx={prev_idx}")
        print(f"DEBUG: current_matches={self.current_matches}")
        
        # Update the delegate with current highlighting state
        self.delegate.set_highlighting(perf_idx, prev_idx, self.current_matches)
        
        # Force table repaint to trigger delegate's paint() method
        self.table.viewport().update()
        print(f"DEBUG: Delegate updated and table repaint triggered")
                        
    def search_columns(self, query: str):
        """Search columns by header text and first data row values."""
        query = query.lower().strip()
        keywords = query.split() if query else []
        
        self.current_matches = []
        
        if not keywords:
            self.match_info.setText("")
            self.match_info.setStyleSheet("color: #94a3b8;")
            self.update_column_highlighting()
            return
            
        # Get first FEW data rows for additional matching (headers might be in row 2 or 3)
        scan_rows = self.data_rows[:5] if self.data_rows else []
        
        for col_idx, header in enumerate(self.headers):
            header_text = str(header).lower()
            
            # Combine header + data from first few rows for search
            data_texts = [str(row[col_idx]).lower() for row in scan_rows if col_idx < len(row)]
            combined = header_text + " " + " ".join(data_texts)
            
            # Check if ALL keywords match
            if all(kw in combined for kw in keywords):
                self.current_matches.append(col_idx)
                
        # Update UI
        if self.current_matches:
            self.match_info.setText(f"✓ {len(self.current_matches)} columns found")
            self.match_info.setStyleSheet("color: #10b981; font-weight: bold;")
            
            # Scroll to first match
            first_match = self.current_matches[0]
            self.table.scrollToItem(self.table.item(0, first_match + 1))
        else:
            self.match_info.setText("✗ No matches")
            self.match_info.setStyleSheet("color: #ef4444;")
            
        self.update_column_highlighting()
            
    def quick_search(self, keyword: str):
        """Add keyword to search or set it."""
        current = self.search_input.text().strip()
        # Toggle: if keyword already in search, remove it; otherwise add it
        if keyword.lower() in current.lower():
            self.search_input.setText(keyword)
        elif current:
            self.search_input.setText(current + " " + keyword)
        else:
            self.search_input.setText(keyword)
            
    def get_selection(self) -> Dict[str, Dict[str, Any]]:
        """Return the selected columns."""
        return {
            "perf": self.selected_perf_col,
            "prev": self.selected_prev_col
        }
