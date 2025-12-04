import sys
from sideBar import Sidebar
from GPSDisplay import GPSWidget
from console import ConsoleWindow
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QSplitter

#color pallette
#background: #0E1935
#buttons: #90E2DD
#highlight: #E3F8F6
#boarders: #562D8B
class MainWindow(QMainWindow):
    loaded_file_path = None
    sourceType = "Bluetooth"

    spliter_syle = """
            QSplitter {
                background-color: #0E1935;
            }
            QSplitter::handle:horizontal {
                background-color: #562D8B;
                width: 2px;
                margin: 2px;
            }
            QSplitter::handle:vertical {
                background-color: #562D8B;
                height: 2px;
                margin: 2px;
            }
        """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Processor")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(self.spliter_syle)
        layout.addWidget(splitter)

        self.sidebar = Sidebar()
        self.sidebar.setMinimumWidth(100)
        self.sidebar.setMaximumWidth(600)
        splitter.addWidget(self.sidebar)
        
        #connect sidebar signals to main window slots
        self.sidebar.sourceType.connect(self.handle_type_selected)
        self.sidebar.sourceFile.connect(self.handle_file_selected)

        middleSpliter = QSplitter(Qt.Vertical)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.GPSDisplay = GPSWidget()
        content_layout.addWidget(self.GPSDisplay)

        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        text_console = ConsoleWindow()
        console_layout.addWidget(text_console)

        middleSpliter.addWidget(content)
        middleSpliter.addWidget(console_widget)
        splitter.addWidget(middleSpliter)

    def handle_type_selected(self, mode):
        print("MainWindow opperating using: " + mode + " mode")
        self.sourceType = mode

    def handle_file_selected(self, path):
        print("MainWindow loaded file: " + path)
        self.loaded_file_path = path


def setupWindow():
        app = QApplication(sys.argv)
        window = MainWindow()
        window.showMaximized()
        sys.exit(app.exec())

if __name__ == "__main__":
    setupWindow()