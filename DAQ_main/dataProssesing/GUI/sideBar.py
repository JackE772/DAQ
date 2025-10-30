from PySide6.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QComboBox, QLabel, QTextEdit, QPushButton
from PySide6.QtCore import Signal
import os

class Sidebar(QWidget):
    # Optional signals so the main window can react to button clicks
    button_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedWidth(400)  # sidebar width
        self.setStyleSheet("""
            QPushButton {
                background-color: #3B4252;
                border: none;
                padding: 8px;
                margin: 4px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #4C566A;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.scourceLable = QLabel("Select Data Source:")
        layout.addWidget(self.scourceLable)
        self.scourceSelector = QComboBox()
        self.scourceSelector.addItems(["Bluetooth", "File", "Simulator (not implemented)"])
        layout.addWidget(self.scourceSelector)

        #file selection UI
        self.fileSelectorLable = QLabel("Select File To read From:")
        self.file_label = QLabel("No file selected")
        self.select_file_button = QPushButton("Select File...")
        self.select_file_button.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.fileSelectorLable)
        layout.addWidget(self.file_label)
        layout.addWidget(self.select_file_button)

        #BLE selection UI
        self.BLELabel = QLabel("BLE ID:")
        self.BLESelector = QTextEdit("CAR_GOES_VROOM")
        self.BLESelector.setFixedHeight(30)
        layout.addWidget(self.BLELabel)
        layout.addWidget(self.BLESelector)

        self.file_ble_UI_switch("Bluetooth")  # set initial state
        self.scourceSelector.currentTextChanged.connect(self.file_ble_UI_switch)

        layout.addStretch()  # push everything up

    def file_ble_UI_switch(self, source):
        if source == "File":
            self.BLELabel.hide()
            self.BLESelector.hide()
            self.file_label.show()
            self.select_file_button.show()
            self.fileSelectorLable.show()
        elif source == "Bluetooth":
            self.BLELabel.show()
            self.BLESelector.show()
            self.file_label.hide()
            self.select_file_button.hide()
            self.fileSelectorLable.hide()
        elif source == "Simulator (not implemented)":
            self.BLELabel.hide()
            self.BLESelector.hide()
            self.file_label.hide()
            self.select_file_button.hide()
            self.fileSelectorLable.hide()

    def open_file_dialog(self):
        # Open a standard file dialog (blocks until closed)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a file",
            "",                           # starting directory ("" = current)
            "CSV Files (*.csv)"  # file filters
        )

        if file_path:  # User selected a file
            filename = os.path.basename(file_path)
            self.file_label.setText(f"Selected: {filename}")
            print("Selected file path:", file_path)