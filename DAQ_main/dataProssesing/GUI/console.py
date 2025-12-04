from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget
import sys

class ConsoleWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout(self)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)  # Make it read-only for output
        self.layout.addWidget(self.console_output)

        # Example: Writing to the console
        self.console_output.append("GPS logger console initialized.")
        
    def log_message(self, message):
        self.console_output.append(message)