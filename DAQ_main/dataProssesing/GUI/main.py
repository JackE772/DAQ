import sys
from sideBar import Sidebar
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QSplitter

#color pallette
#background: #0E1935
#buttons: #90E2DD
#highlight: #E3F8F6
#boarders: #562D8B
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Processor")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter {
                background-color: #0E1935;  /* same as window bg */
            }
            QSplitter::handle {
                background-color: #562D8B;  /* slightly lighter for subtle contrast */
                width: 5px;                 /* thin flat line */
                margin: 5px;
            }
            """)
        layout.addWidget(splitter)

        self.sidebar = Sidebar()
        splitter.addWidget(self.sidebar)
        #self.sidebar.button_clicked.connect(self.handle_sidebar_click)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(QPushButton("Button 1"))
        content_layout.addWidget(QPushButton("Button 2"))
        splitter.addWidget(content)

        self.sidebar.setMinimumWidth(100)
        self.sidebar.setMaximumWidth(600)


def setupWindow():
        app = QApplication(sys.argv)
        window = MainWindow()
        window.showMaximized()
        sys.exit(app.exec())

if __name__ == "__main__":
    setupWindow()