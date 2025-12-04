import asyncio
from curses import window
import math
import sys
from sideBar import Sidebar
from GPSDisplay import GPSWidget
from console import ConsoleWindow
from ble_getter import DataGetter
from speedometer import SpeedometerWidget
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QSplitter
from qasync import QEventLoop, asyncSlot

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
        
        self.speedometer = SpeedometerWidget()
        layout.addWidget(self.speedometer)
        
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
        self.text_console = ConsoleWindow()
        console_layout.addWidget(self.text_console)

        middleSpliter.addWidget(content)
        middleSpliter.addWidget(console_widget)
        splitter.addWidget(middleSpliter)

    def handle_type_selected(self, mode):
        print("MainWindow opperating using: " + mode + " mode")
        self.sourceType = mode

    def handle_file_selected(self, path):
        print("MainWindow loaded file: " + path)
        self.loaded_file_path = path
    
async def async_ble_loop(window):
    data_getter = DataGetter()
    connected = await data_getter.connect(logger=window.text_console)
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
    
    with loop:
        loop.run_forever()
    

if __name__ == "__main__":
    main()
    