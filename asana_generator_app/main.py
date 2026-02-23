import sys
import logging
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow

# Configure logging
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, 'asana_generator.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('AsanaGenerator')


def main():
    app = QApplication(sys.argv)
    
    try:
        window = MainWindow()
        window.showMaximized()
        logger.info("Application started successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize application: {e}", exc_info=True)
        QMessageBox.critical(None, "Startup Error", 
            f"Failed to start the application:\n{str(e)}\n\nCheck {LOG_FILE} for details.")
        sys.exit(1)
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
