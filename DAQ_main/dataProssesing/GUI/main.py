#using asyncio for asynchronous programming this is deprecated and included in python
#TODO refacter to avoid using asyncio
import asyncio

import math
import sys
from sideBar import Sidebar
from GPSDisplay import GPSWidget
from console import ConsoleWindow
from ble_getter import DataGetter
from speedometer import SpeedometerWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QSplitter
from qasync import QEventLoop, asyncSlot

#color pallette
background = "#0F0000"
buttons = "#90E2DD"
highlight = "#E3F8F6"
borders = "#7a0b0b"
class MainWindow(QMainWindow):
    loaded_file_path = None
    gps_updated = Signal(str)
    sourceType = "Bluetooth"
    playback = Signal(bool)

    spliter_syle = f"""
            QSplitter {{
                background-color: {background};
            }}
            QSplitter::handle:horizontal {{
                background-color: {borders};
                width: 2px;
                margin: 2px;
            }}
            QSplitter::handle:vertical {{
                background-color: {borders};
                height: 2px;
                margin: 2px;
            }}
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

        #self.speedometer = SpeedometerWidget()
        #layout.addWidget(self.speedometer)

        #connect sidebar signals to main window slots
        self.sidebar.sourceType.connect(self.handle_type_selected)
        self.sidebar.sourceFile.connect(self.handle_file_selected)

        middleSpliter = QSplitter(Qt.Vertical)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.GPSDisplay = GPSWidget(self)
        content_layout.addWidget(self.GPSDisplay)
        self.playbackButton = QPushButton("play")
        self.playbackButton.clicked.connect(self.start_playback)
        self.pausePlaybackButton = QPushButton("pause")
        self.pausePlaybackButton.clicked.connect(self.pause_playback)
        self.buttonContent = QWidget()
        self.buttonContent.setMaximumHeight(50)
        playbackLayout = QHBoxLayout(self.buttonContent)
        playbackLayout.addWidget(self.playbackButton)
        playbackLayout.addWidget(self.pausePlaybackButton)
        content_layout.addWidget(self.buttonContent)

        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        self.text_console = ConsoleWindow()
        console_layout.addWidget(self.text_console)

        middleSpliter.addWidget(content)
        middleSpliter.addWidget(console_widget)
        splitter.addWidget(middleSpliter)

        rightSideSlider = QSplitter(Qt.Vertical)
        self.speedometer = SpeedometerWidget(self.GPSDisplay, main_window=self)
        rightSideSlider.addWidget(self.speedometer)
        splitter.addWidget(rightSideSlider)

    def handle_type_selected(self, mode):
        print(f"MainWindow opperating using: {mode} mode")
        self.sourceType = mode

    def handle_file_selected(self, path):
        print(f"MainWindow loaded file: {path}")
        self.loaded_file_path = path

    def start_playback(self):
        self.playback.emit(True)

    def pause_playback(self):
        self.playback.emit(False)

def emit_GPS_pos_from_file(window):
    window.gps_updated.emit(window.loaded_file_path)

async def async_update_GPS_pos(window):
    window.text_console.log_message("seting up GPS data loging from file")

    while True:
        await asyncio.sleep(0.5)
        if(window.loaded_file_path != None):
            window.text_console.log_message(f"loading GPS position from {window.loaded_file_path}")
            break

    emit_GPS_pos_from_file(window)

async def async_ble_loop(window):
    data_getter = DataGetter()
    connected = await data_getter.connect(logger=window.text_console)
    window.text_console.log_message("seting up BLE data streaming")

    if not connected:
        window.text_console.log_message("Failed to connect BLE")
        return

    try:
        while True:
            gps_data = await data_getter.read_gps_status()
            imu_data = await data_getter.read_imu_data()

            window.text_console.log_message(f"GPS Data: {gps_data}")
            window.text_console.log_message(f"IMU Data: {imu_data}")

            speed = math.sqrt(gps_data["vx"]**2 + gps_data["vy"]**2)

            window.GPSDisplay.speedometer.set_speed(speed)

            await asyncio.sleep(0.5)  # poll every 0.5 seconds
    finally:
        await data_getter.disconnect(logger=window.text_console)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()

    # Integrate asyncio loop with Qt
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    loop.create_task(async_ble_loop(window))
    loop.create_task(async_update_GPS_pos(window))

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()