#!/usr/bin/env python3
"""
Asana CSV Generator - PyQt5 Application
Creates CSV files in Asana import format for Section/Task/Sub-task hierarchy
"""

import sys
import csv
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QLabel, QLineEdit, 
                            QTextEdit, QComboBox, QSpinBox, QPushButton, 
                            QTableWidget, QTableWidgetItem, QTabWidget,
                            QGroupBox, QFileDialog, QMessageBox, QTreeWidget,
                            QTreeWidgetItem, QCheckBox, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon

class AsanaCSVGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asana CSV Generator - Test Management")
        self.setGeometry(100, 100, 1200, 800)
        
        # Data storage
        self.project_data = {
            'name': '',
            'sections': [],
            'tasks': [],
            'subtasks': []
        }
        
        # Fixed columns for Asana CSV format
        self.csv_headers = [
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
            "iteration_10", "Iteration count", "Perf_BRD", "Previous Value", 
            "me", "Projects (imported)", "Parent task"
        ]
        
        self.setup_ui()
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Tab widget
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # Create tabs
        self.create_project_tab(tab_widget)
        self.create_sections_tab(tab_widget)
        self.create_tasks_tab(tab_widget)
        self.create_preview_tab(tab_widget)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        generate_btn = QPushButton("Generate CSV")
        generate_btn.clicked.connect(self.generate_csv)
        generate_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all_data)
        
        load_btn = QPushButton("Load Template")
        load_btn.clicked.connect(self.load_template)
        
        button_layout.addWidget(load_btn)
        button_layout.addStretch()
        button_layout.addWidget(clear_btn)
        button_layout.addWidget(generate_btn)
        
        main_layout.addLayout(button_layout)
        
    def create_project_tab(self, tab_widget):
        project_tab = QWidget()
        tab_widget.addTab(project_tab, "Project Settings")
        
        layout = QVBoxLayout(project_tab)
        
        # Project Information Group
        project_group = QGroupBox("Project Information")
        project_layout = QGridLayout(project_group)
        
        project_layout.addWidget(QLabel("Project Name:"), 0, 0)
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("e.g., J19.2 SBR J19.3 Mainline")
        project_layout.addWidget(self.project_name_edit, 0, 1)
        
        project_layout.addWidget(QLabel("Description:"), 1, 0)
        self.project_desc_edit = QTextEdit()
        self.project_desc_edit.setMaximumHeight(80)
        self.project_desc_edit.setPlaceholderText("Optional project description")
        project_layout.addWidget(self.project_desc_edit, 1, 1)
        
        layout.addWidget(project_group)
        
        # Default Settings Group
        defaults_group = QGroupBox("Default Settings")
        defaults_layout = QGridLayout(defaults_group)
        
        # Priority options
        defaults_layout.addWidget(QLabel("Default Priority:"), 0, 0)
        self.default_priority_combo = QComboBox()
        self.default_priority_combo.addItems(["P0", "P1", "P2", "P3", "OOBE", "GEN Ai", 
                                            "HWR Existing", "HWR New", "NRS", "Keyboard Canvas",
                                            "Color Stroke", "HWR search", "Q & A", "Sidepanel"])
        defaults_layout.addWidget(self.default_priority_combo, 0, 1)
        
        # Default device
        defaults_layout.addWidget(QLabel("Default Device:"), 1, 0)
        self.default_device_combo = QComboBox()
        self.default_device_combo.addItems(["", "Malbec", "Cava", "Barolo", "Rossini", 
                                          "Sangria", "Pisco", "Seabreeze", "Gibson", 
                                          "Paloma", "Calvados"])
        self.default_device_combo.setEditable(True)
        defaults_layout.addWidget(self.default_device_combo, 1, 1)
        
        # Default estimated time
        defaults_layout.addWidget(QLabel("Default Time (minutes):"), 2, 0)
        self.default_time_spin = QSpinBox()
        self.default_time_spin.setRange(1, 300)
        self.default_time_spin.setValue(15)
        self.default_time_spin.setSuffix(" min")
        defaults_layout.addWidget(self.default_time_spin, 2, 1)
        
        layout.addWidget(defaults_group)
        layout.addStretch()
        
    def create_sections_tab(self, tab_widget):
        sections_tab = QWidget()
        tab_widget.addTab(sections_tab, "Sections")
        
        layout = QVBoxLayout(sections_tab)
        
        # Add section controls
        add_section_group = QGroupBox("Add New Section")
        add_layout = QGridLayout(add_section_group)
        
        add_layout.addWidget(QLabel("Section Name:"), 0, 0)
        self.section_name_edit = QLineEdit()
        self.section_name_edit.setPlaceholderText("e.g., Week_05 J19.2")
        add_layout.addWidget(self.section_name_edit, 0, 1)
        
        add_section_btn = QPushButton("Add Section")
        add_section_btn.clicked.connect(self.add_section)
        add_layout.addWidget(add_section_btn, 0, 2)
        
        layout.addWidget(add_section_group)
        
        # Sections list
        sections_group = QGroupBox("Project Sections")
        sections_layout = QVBoxLayout(sections_group)
        
        self.sections_tree = QTreeWidget()
        self.sections_tree.setHeaderLabel("Sections")
        sections_layout.addWidget(self.sections_tree)
        
        # Section controls
        section_controls = QHBoxLayout()
        edit_section_btn = QPushButton("Edit Selected")
        delete_section_btn = QPushButton("Delete Selected")
        edit_section_btn.clicked.connect(self.edit_section)
        delete_section_btn.clicked.connect(self.delete_section)
        
        section_controls.addWidget(edit_section_btn)
        section_controls.addWidget(delete_section_btn)
        section_controls.addStretch()
        
        sections_layout.addLayout(section_controls)
        layout.addWidget(sections_group)
        
    def create_tasks_tab(self, tab_widget):
        tasks_tab = QWidget()
        tab_widget.addTab(tasks_tab, "Tasks & Subtasks")
        
        layout = QVBoxLayout(tasks_tab)
        
        # Task creation controls
        task_group = QGroupBox("Add Tasks")
        task_layout = QGridLayout(task_group)
        
        # Section selection
        task_layout.addWidget(QLabel("Section:"), 0, 0)
        self.task_section_combo = QComboBox()
        task_layout.addWidget(self.task_section_combo, 0, 1)
        
        # Parent task (optional)
        task_layout.addWidget(QLabel("Parent Task:"), 1, 0)
        self.parent_task_edit = QLineEdit()
        self.parent_task_edit.setPlaceholderText("Leave empty for main tasks, or enter parent task name")
        task_layout.addWidget(self.parent_task_edit, 1, 1)
        
        # Task name
        task_layout.addWidget(QLabel("Task Name:"), 2, 0)
        self.task_name_edit = QLineEdit()
        self.task_name_edit.setPlaceholderText("Enter task description")
        task_layout.addWidget(self.task_name_edit, 2, 1)
        
        # Task settings row 1
        settings_layout1 = QHBoxLayout()
        
        settings_layout1.addWidget(QLabel("Priority:"))
        self.task_priority_combo = QComboBox()
        self.task_priority_combo.addItems(["P0", "P1", "P2", "P3", "OOBE", "GEN Ai", 
                                         "HWR Existing", "HWR New", "NRS", "Keyboard Canvas",
                                         "Color Stroke", "HWR search", "Q & A", "Sidepanel"])
        settings_layout1.addWidget(self.task_priority_combo)
        
        settings_layout1.addWidget(QLabel("Time (min):"))
        self.task_time_spin = QSpinBox()
        self.task_time_spin.setRange(1, 300)
        self.task_time_spin.setValue(15)
        settings_layout1.addWidget(self.task_time_spin)
        
        settings_layout1.addWidget(QLabel("Device:"))
        self.task_device_combo = QComboBox()
        self.task_device_combo.addItems(["", "Malbec", "Cava", "Barolo", "Rossini", 
                                       "Sangria", "Pisco", "Seabreeze", "Gibson", 
                                       "Paloma", "Calvados"])
        self.task_device_combo.setEditable(True)
        settings_layout1.addWidget(self.task_device_combo)
        
        task_layout.addLayout(settings_layout1, 3, 0, 1, 2)
        
        # Add task button
        add_task_btn = QPushButton("Add Task")
        add_task_btn.clicked.connect(self.add_task)
        add_task_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
        task_layout.addWidget(add_task_btn, 4, 0, 1, 2)
        
        layout.addWidget(task_group)
        
        # Tasks tree view
        tasks_tree_group = QGroupBox("Project Structure")
        tree_layout = QVBoxLayout(tasks_tree_group)
        
        self.tasks_tree = QTreeWidget()
        self.tasks_tree.setHeaderLabels(["Task/Section", "Priority", "Time", "Device"])
        tree_layout.addWidget(self.tasks_tree)
        
        # Tree controls
        tree_controls = QHBoxLayout()
        delete_task_btn = QPushButton("Delete Selected")
        duplicate_task_btn = QPushButton("Duplicate Selected")
        delete_task_btn.clicked.connect(self.delete_task)
        duplicate_task_btn.clicked.connect(self.duplicate_task)
        
        tree_controls.addWidget(delete_task_btn)
        tree_controls.addWidget(duplicate_task_btn)
        tree_controls.addStretch()
        
        tree_layout.addLayout(tree_controls)
        layout.addWidget(tasks_tree_group)
        
    def create_preview_tab(self, tab_widget):
        preview_tab = QWidget()
        tab_widget.addTab(preview_tab, "Preview")
        
        layout = QVBoxLayout(preview_tab)
        
        # Preview controls
        preview_controls = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Preview")
        refresh_btn.clicked.connect(self.refresh_preview)
        
        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_csv)
        export_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; }")
        
        preview_controls.addWidget(refresh_btn)
        preview_controls.addStretch()
        preview_controls.addWidget(export_btn)
        
        layout.addLayout(preview_controls)
        
        # Preview table
        self.preview_table = QTableWidget()
        layout.addWidget(self.preview_table)
        
        # Stats
        self.stats_label = QLabel("Statistics will appear here")
        layout.addWidget(self.stats_label)
        
    def add_section(self):
        section_name = self.section_name_edit.text().strip()
        if not section_name:
            QMessageBox.warning(self, "Warning", "Please enter a section name")
            return
            
        # Add to sections list
        self.project_data['sections'].append(section_name)
        
        # Update UI
        item = QTreeWidgetItem([section_name])
        self.sections_tree.addTopLevelItem(item)
        
        # Update task section combo
        self.task_section_combo.addItem(section_name)
        
        self.section_name_edit.clear()
        
    def add_task(self):
        section = self.task_section_combo.currentText()
        parent_task = self.parent_task_edit.text().strip()
        task_name = self.task_name_edit.text().strip()
        priority = self.task_priority_combo.currentText()
        time_minutes = self.task_time_spin.value()
        device = self.task_device_combo.currentText()
        
        if not section or not task_name:
            QMessageBox.warning(self, "Warning", "Please select section and enter task name")
            return
            
        # Format time as HH:MM
        time_str = f"{time_minutes//60}:{time_minutes%60:02d}"
        
        task_data = {
            'section': section,
            'parent_task': parent_task,
            'name': task_name,
            'priority': priority,
            'estimated_time': time_str,
            'device': device,
            'project': self.project_name_edit.text().strip()
        }
        
        self.project_data['tasks'].append(task_data)
        
        # Add to tree
        item = QTreeWidgetItem([task_name, priority, time_str, device])
        
        if parent_task:
            # Find parent in tree
            parent_item = None
            root = self.tasks_tree.invisibleRootItem()
            for i in range(root.childCount()):
                child = root.child(i)
                if child.text(0) == parent_task:
                    parent_item = child
                    break
            
            if parent_item:
                parent_item.addChild(item)
            else:
                # Create parent if not found
                parent_item = QTreeWidgetItem([parent_task, "", "", ""])
                self.tasks_tree.addTopLevelItem(parent_item)
                parent_item.addChild(item)
        else:
            self.tasks_tree.addTopLevelItem(item)
            
        # Expand tree
        self.tasks_tree.expandAll()
        
        # Clear inputs
        self.task_name_edit.clear()
        self.parent_task_edit.clear()
        
    def edit_section(self):
        current = self.sections_tree.currentItem()
        if current:
            # Simple edit - could be enhanced with dialog
            old_name = current.text(0)
            new_name, ok = QMessageBox.getText(self, "Edit Section", "Section name:", text=old_name)
            if ok and new_name.strip():
                current.setText(0, new_name.strip())
                # Update in data
                if old_name in self.project_data['sections']:
                    idx = self.project_data['sections'].index(old_name)
                    self.project_data['sections'][idx] = new_name.strip()
                    
    def delete_section(self):
        current = self.sections_tree.currentItem()
        if current:
            section_name = current.text(0)
            reply = QMessageBox.question(self, "Confirm Delete", 
                                       f"Delete section '{section_name}' and all its tasks?")
            if reply == QMessageBox.Yes:
                # Remove from tree
                root = self.sections_tree.invisibleRootItem()
                root.removeChild(current)
                
                # Remove from data
                if section_name in self.project_data['sections']:
                    self.project_data['sections'].remove(section_name)
                    
    def delete_task(self):
        current = self.tasks_tree.currentItem()
        if current:
            task_name = current.text(0)
            reply = QMessageBox.question(self, "Confirm Delete", 
                                       f"Delete task '{task_name}'?")
            if reply == QMessageBox.Yes:
                # Remove from tree
                parent = current.parent()
                if parent:
                    parent.removeChild(current)
                else:
                    root = self.tasks_tree.invisibleRootItem()
                    root.removeChild(current)
                    
    def duplicate_task(self):
        current = self.tasks_tree.currentItem()
        if current:
            # Create duplicate with " (Copy)" suffix
            new_name = current.text(0) + " (Copy)"
            new_item = QTreeWidgetItem([new_name, current.text(1), current.text(2), current.text(3)])
            
            parent = current.parent()
            if parent:
                parent.addChild(new_item)
            else:
                self.tasks_tree.addTopLevelItem(new_item)
                
    def refresh_preview(self):
        """Generate preview of CSV data"""
        csv_data = self.generate_csv_data()
        
        # Update table
        self.preview_table.setRowCount(len(csv_data))
        self.preview_table.setColumnCount(len(self.csv_headers))
        self.preview_table.setHorizontalHeaderLabels(self.csv_headers)
        
        for row, row_data in enumerate(csv_data):
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.preview_table.setItem(row, col, item)
                
        # Update stats
        total_rows = len(csv_data)
        sections_count = len(self.project_data['sections'])
        tasks_count = len(self.project_data['tasks'])
        
        self.stats_label.setText(f"Total Rows: {total_rows} | Sections: {sections_count} | Tasks: {tasks_count}")
        
    def generate_csv_data(self):
        """Generate the actual CSV data structure"""
        rows = []
        project_name = self.project_name_edit.text().strip()
        
        for section in self.project_data['sections']:
            for task in self.project_data['tasks']:
                if task['section'] == section:
                    row = [""] * len(self.csv_headers)  # Initialize empty row
                    
                    # Fill known columns
                    row[4] = task['name']  # Name
                    row[5] = section if not task['parent_task'] else ""  # Section/Column
                    row[12] = project_name  # Projects
                    row[13] = task['parent_task']  # Parent task
                    row[16] = task['estimated_time']  # Estimated time
                    row[18] = task['priority']  # Priority
                    
                    # Add device info
                    if task['device']:
                        row[31] = task['device']  # Devices
                        
                    # Add default performance values
                    row[20] = "0"      # Iteration_01
                    row[25] = "0"      # Average
                    row[26] = "0.1"    # Perf_BRD
                    row[27] = "0.1"    # Deviation % Current Vs BRD
                    
                    rows.append(row)
                    
        return rows
        
    def generate_csv(self):
        """Main CSV generation function"""
        if not self.project_data['sections'] or not self.project_data['tasks']:
            QMessageBox.warning(self, "Warning", "Please add at least one section and one task")
            return
            
        self.export_csv()
        
    def export_csv(self):
        """Export CSV to file"""
        filename, _ = QFileDialog.getSaveFileName(self, "Save CSV File", 
                                                f"asana_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                                "CSV files (*.csv)")
        if filename:
            try:
                csv_data = self.generate_csv_data()
                
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(self.csv_headers)  # Write headers
                    writer.writerows(csv_data)  # Write data
                    
                QMessageBox.information(self, "Success", 
                                      f"CSV file exported successfully!\n{filename}")
                                      
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export CSV:\n{str(e)}")
                
    def clear_all_data(self):
        """Clear all data"""
        reply = QMessageBox.question(self, "Confirm Clear", 
                                   "Clear all data? This cannot be undone.")
        if reply == QMessageBox.Yes:
            self.project_data = {'name': '', 'sections': [], 'tasks': [], 'subtasks': []}
            self.project_name_edit.clear()
            self.project_desc_edit.clear()
            self.sections_tree.clear()
            self.tasks_tree.clear()
            self.task_section_combo.clear()
            self.preview_table.setRowCount(0)
            
    def load_template(self):
        """Load a predefined template"""
        # Add some sample data
        self.project_name_edit.setText("J19.2 SBR J19.3 Mainline")
        
        # Add sample sections
        sample_sections = ["Week_05 J19.2", "Week_05 J19.3"]
        for section in sample_sections:
            self.project_data['sections'].append(section)
            item = QTreeWidgetItem([section])
            self.sections_tree.addTopLevelItem(item)
            self.task_section_combo.addItem(section)
            
        QMessageBox.information(self, "Template Loaded", "Sample template loaded successfully!")

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = AsanaCSVGenerator()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
