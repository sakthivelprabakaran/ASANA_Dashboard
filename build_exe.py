"""Build script for PyInstaller packaging."""
import PyInstaller.__main__
import os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PyInstaller.__main__.run([
    'asana_generator_app/main.py',
    '--onedir',
    '--windowed', 
    '--name=AsanaCSVGenerator',
    '--paths=asana_generator_app',
    '--hidden-import=ui.main_window',
    '--hidden-import=ui.brd_viewer_dialog',
    '--hidden-import=ui.report_generator_tab',
    '--hidden-import=ui.settings_dialog',
    '--hidden-import=ui.manual_subtask_dialog',
    '--hidden-import=core.config_manager',
    '--hidden-import=core.data_loader',
    '--hidden-import=core.brd_matcher',
    '--hidden-import=core.brd_writer',
    '--hidden-import=core.csv_importer',
    '--add-data=asana_generator_app/resources;resources',
    '--add-data=asana_generator_app/ui/styles.qss;ui',
    '--noconfirm',
])