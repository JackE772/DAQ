from PySide6.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QComboBox, QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
import os

class Sidebar(QWidget):
    sourceType = Signal(str)

    sourceFile = Signal(str)

    def __init__(self, main_window=None, brand_logo_path=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.brand_logo_path = brand_logo_path
        self.brand_logo_pixmap = QPixmap(self.brand_logo_path) if self.brand_logo_path else None
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.brandBanner = QFrame()
        self.brandBanner.setObjectName("sidebarBrandBanner")
        self.brandBanner.setMinimumHeight(56)
        self.brandBanner.setMaximumHeight(68)
        brand_layout = QVBoxLayout(self.brandBanner)
        brand_layout.setContentsMargins(4, 2, 4, 2)
        brand_layout.setSpacing(0)

        self.brandLogoLabel = QLabel("AE MOTORSPORTS")
        self.brandLogoLabel.setObjectName("sidebarBrandLogoLabel")
        self.brandLogoLabel.setAlignment(Qt.AlignCenter)
        self.brandLogoLabel.setMinimumHeight(44)
        brand_layout.addWidget(self.brandLogoLabel)
        layout.addWidget(self.brandBanner)

        self.scourceLable = QLabel("Select Data Source:")
        layout.addWidget(self.scourceLable)
        self.scourceSelector = QComboBox()
        self.scourceSelector.setObjectName("sourceSelector")
        self.scourceSelector.addItems(["Bluetooth", "File"])
        dropdown_indicator_path = os.path.join(os.path.dirname(__file__), "dropdown_indicator.svg").replace("\\", "/")
        self.scourceSelector.setStyleSheet(
            f"QComboBox#sourceSelector {{"
            " background-color: #120707;"
            " color: #f4e8e8;"
            " border: 1px solid #6a2e2e;"
            " border-radius: 6px;"
            " padding: 5px 30px 5px 8px;"
            "}"
            "QComboBox#sourceSelector::drop-down {"
            " border: none;"
            " width: 24px;"
            " subcontrol-origin: padding;"
            " subcontrol-position: top right;"
            "}"
            f"QComboBox#sourceSelector::down-arrow {{"
            f" image: url({dropdown_indicator_path});"
            " width: 14px;"
            " height: 14px;"
            "}"
            "QComboBox#sourceSelector QAbstractItemView {"
            " background-color: #120707;"
            " color: #f4e8e8;"
            " selection-background-color: #c04f4f;"
            " border: 1px solid #6a2e2e;"
            " outline: 0px;"
            "}"
        )
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
        self.BLESelector = QLineEdit("CAR_GOES_VROOM")
        layout.addWidget(self.BLELabel)
        layout.addWidget(self.BLESelector)

        self._apply_source_widgets("Bluetooth")
        self.scourceSelector.currentTextChanged.connect(self.file_ble_UI_switch)

        self.apply_brand_styles()
        self.update_brand_logo()

        layout.addStretch()  # push everything up

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_brand_logo()

    def apply_brand_styles(self):
        self.brandBanner.setStyleSheet(
            "QFrame#sidebarBrandBanner {"
            " background-color: #050202;"
            " border: none;"
            "}"
            "QLabel#sidebarBrandLogoLabel {"
            " color: #f4e8e8;"
            " font-size: 18px;"
            " font-weight: 700;"
            " letter-spacing: 1px;"
            "}"
        )

    def update_brand_logo(self):
        if not self.brand_logo_pixmap or self.brand_logo_pixmap.isNull():
            self.brandLogoLabel.setText("AE MOTORSPORTS")
            self.brandLogoLabel.setPixmap(QPixmap())
            return

        target_width = min(280, max(160, self.brandLogoLabel.width() - 14))
        target_height = min(46, max(28, self.brandLogoLabel.height() - 2))
        scaled = self.brand_logo_pixmap.scaled(
            target_width,
            target_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.brandLogoLabel.setText("")
        self.brandLogoLabel.setPixmap(scaled)

    def _apply_source_widgets(self, source):
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

    def file_ble_UI_switch(self, source):
        self._apply_source_widgets(source)
        self.sourceType.emit(source)

    def set_source_mode(self, source):
        current_state = self.scourceSelector.blockSignals(True)
        try:
            self.scourceSelector.setCurrentText(source)
        finally:
            self.scourceSelector.blockSignals(current_state)

        self._apply_source_widgets(source)

    def open_file_dialog(self):
        # Open a standard file dialog (blocks until closed)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a file",
            "",                           # starting directory ("" = current)
            (
                "Data Files (*.csv *.txt *.log *.tsv *.dat);;"
                "CSV Files (*.csv);;"
                "Text/Log Files (*.txt *.log *.tsv *.dat);;"
                "All Files (*)"
            )
        )

        if file_path:  # User selected a file
            filename = os.path.basename(file_path)
            self.file_label.setText(f"Selected: {filename}")
            self.sourceFile.emit(file_path)