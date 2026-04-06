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
from acceleration_chart import AccelerationChart
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
        self.sidebar.setMaximumWidth(300)
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
        console_widget.setFixedHeight(500)
        console_widget.setMinimumHeight(100)
        console_widget.setMaximumHeight(300)

        middleSpliter.addWidget(content)
        middleSpliter.addWidget(console_widget)
        splitter.addWidget(middleSpliter)

        rightSideSlider = QSplitter(Qt.Vertical)
        self.speedometer = SpeedometerWidget(self.GPSDisplay, main_window=self)
        rightSideSlider.setFixedWidth(350)
        rightSideSlider.addWidget(self.speedometer)

        self.acceleration_chart = AccelerationChart(self.GPSDisplay)
        self.GPSDisplay.output_acceleration.connect(self.acceleration_chart.add_acceleration)
        rightSideSlider.addWidget(self.acceleration_chart)
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
    window.text_console.log_message("File loader task started. Waiting for File mode.", level="INFO")

    while True:
        if window.sourceType != "File":
            await asyncio.sleep(0.5)
            continue

        await asyncio.sleep(0.5)
        if(window.loaded_file_path != None):
            window.text_console.log_message(
                f"File selected. Loading GPS data from {window.loaded_file_path}",
                level="SUCCESS"
            )
            break

    emit_GPS_pos_from_file(window)

async def async_ble_loop(window):
    data_getter = DataGetter()
    window.text_console.log_message("BLE loop started. Waiting for Bluetooth mode.", level="INFO")
    reconnect_delay_seconds = 2.0
    live_playback_started = False
    last_mode = None
    prev_gps_sample = None
    prev_gps_velocity = None

    try:
        while True:
            try:
                if window.sourceType != last_mode:
                    if window.sourceType == "Bluetooth":
                        window.text_console.log_message("Bluetooth mode active. Preparing live stream.", level="INFO")
                    elif window.sourceType == "File":
                        window.text_console.log_message("File mode active. BLE polling paused.", level="WARN")
                    else:
                        window.text_console.log_message(
                            f"{window.sourceType} mode active. BLE polling paused.",
                            level="WARN"
                        )
                    last_mode = window.sourceType

                if window.sourceType != "Bluetooth":
                    live_playback_started = False
                    prev_gps_sample = None
                    prev_gps_velocity = None
                    if data_getter.is_connected():
                        window.text_console.log_message(
                            "Bluetooth mode disabled. Disconnecting BLE client.",
                            level="WARN"
                        )
                        await data_getter.disconnect(logger=window.text_console)
                    await asyncio.sleep(0.5)
                    continue

                if not data_getter.is_connected():
                    window.text_console.log_message("BLE disconnected. Attempting to connect...", level="WARN")
                    connected = await data_getter.connect(logger=window.text_console)
                    if not connected:
                        window.text_console.log_message(
                            f"BLE target unavailable. Retrying connection in {reconnect_delay_seconds:.1f}s",
                            level="WARN"
                        )
                        await asyncio.sleep(reconnect_delay_seconds)
                        continue
                    window.text_console.log_message("BLE connected. Starting live playback.", level="SUCCESS")
                    if not live_playback_started:
                        window.GPSDisplay.configure_for_live_mode()
                        window.start_playback()
                        live_playback_started = True

                gps_data = await data_getter.read_gps_status()
                imu_data = await data_getter.read_imu_data()
                now_s = asyncio.get_running_loop().time()

                if imu_data is not None:
                    speed = math.sqrt(imu_data["vx"]**2 + imu_data["vy"]**2)
                    gps_state = "available" if gps_data is not None else "unavailable"
                    window.text_console.log_message(
                        f"BLE poll complete. GPS {gps_state}. Speed {speed:.2f} m/s",
                        level="DEBUG"
                    )

                    live_point = dict(imu_data)
                    if gps_data is not None:
                        live_point["lat"] = gps_data["lat"]
                        live_point["lon"] = gps_data["lon"]
                        prev_gps_sample = {
                            "lat": gps_data["lat"],
                            "lon": gps_data["lon"],
                            "t": now_s,
                        }
                        prev_gps_velocity = {
                            "vx": imu_data["vx"],
                            "vy": imu_data["vy"],
                        }
                    window.GPSDisplay.load_data_point(live_point)
                    if live_playback_started:
                        window.start_playback()
                else:
                    if gps_data is not None and prev_gps_sample is not None:
                        dt = now_s - prev_gps_sample["t"]
                        if dt > 0:
                            lat = gps_data["lat"]
                            lon = gps_data["lon"]
                            prev_lat = prev_gps_sample["lat"]
                            prev_lon = prev_gps_sample["lon"]

                            meters_per_deg_lat = 111_320.0
                            meters_per_deg_lon = 111_320.0 * math.cos(math.radians((lat + prev_lat) / 2.0))

                            dx = (lon - prev_lon) * meters_per_deg_lon
                            dy = (lat - prev_lat) * meters_per_deg_lat
                            vx = dx / dt
                            vy = dy / dt

                            if prev_gps_velocity is None:
                                ax_w = 0.0
                                ay_w = 0.0
                            else:
                                ax_w = (vx - prev_gps_velocity["vx"]) / dt
                                ay_w = (vy - prev_gps_velocity["vy"]) / dt

                            live_point = {
                                "vx": vx,
                                "vy": vy,
                                "ax_w": ax_w,
                                "ay_w": ay_w,
                                "x": 0.0,
                                "y": 0.0,
                                "lat": lat,
                                "lon": lon,
                            }
                            window.GPSDisplay.load_data_point(live_point)
                            if live_playback_started:
                                window.start_playback()

                            gps_speed = math.sqrt(vx**2 + vy**2)
                            window.text_console.log_message(
                                f"IMU unavailable. Using GPS-estimated motion. Speed {gps_speed:.2f} m/s",
                                level="WARN"
                            )

                            prev_gps_velocity = {
                                "vx": vx,
                                "vy": vy,
                            }
                            prev_gps_sample = {
                                "lat": lat,
                                "lon": lon,
                                "t": now_s,
                            }
                        else:
                            window.text_console.log_message(
                                "IMU unavailable. GPS fallback skipped due to invalid dt.",
                                level="WARN"
                            )
                    elif gps_data is not None:
                        prev_gps_sample = {
                            "lat": gps_data["lat"],
                            "lon": gps_data["lon"],
                            "t": now_s,
                        }
                        prev_gps_velocity = None
                        window.text_console.log_message(
                            "IMU unavailable. Captured first GPS sample for fallback estimation.",
                            level="WARN"
                        )
                    else:
                        window.text_console.log_message(
                            "BLE poll incomplete. IMU and GPS payload unavailable.",
                            level="WARN"
                        )
                    
                    
                    
                    
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                window.text_console.log_message(f"BLE polling error: {exc}", level="ERROR")
                await data_getter.disconnect(logger=window.text_console)
                live_playback_started = False
                prev_gps_sample = None
                prev_gps_velocity = None
                window.text_console.log_message(
                    f"Connection lost. Reconnecting in {reconnect_delay_seconds:.1f}s",
                    level="WARN"
                )
                await asyncio.sleep(reconnect_delay_seconds)
                continue

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