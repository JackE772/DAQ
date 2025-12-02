import sys
from sideBar import Sidebar
from GPSDisplay import GPS_Window
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QSplitter

#color pallette
#background: #0E1935
#buttons: #90E2DD
#highlight: #E3F8F6
#boarders: #562D8B
class MainWindow(QMainWindow):

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
        #self.sidebar.button_clicked.connect(self.handle_sidebar_click)

        middleSpliter = QSplitter(Qt.Vertical)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(QPushButton("Button 1"))
        middleSpliter.addWidget(QPushButton("Button 2"))
        middleSpliter.addWidget(content)
        middleSpliter.setSizes([100, 300])
        splitter.addWidget(middleSpliter)


def setupWindow():
        app = QApplication(sys.argv)
        window = MainWindow()
        window.showMaximized()
        sys.exit(app.exec())

if __name__ == "__main__":
    setupWindow()