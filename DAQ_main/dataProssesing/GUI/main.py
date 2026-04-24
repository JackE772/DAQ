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
from vcu_time_charts import VCUGraphPanel
from vcu_widget import VCUStatusWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QSplitter, QStackedWidget, QSlider, QLabel, QInputDialog
from qasync import QEventLoop, asyncSlot

#color pallette
background = "#0F0000"
buttons = "#90E2DD"
highlight = "#E3F8F6"
borders = "#7a0b0b"
class MainWindow(QMainWindow):
    loaded_file_path = None
    gps_updated = Signal(str)
    vcu_telemetry_updated = Signal(dict)
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

        self.is_playing = False
        self.slider_is_scrubbing = False
        self.resume_after_scrub = False
        self.updating_timeline_ui = False
        self.current_display_mode = "map"

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(self.spliter_syle)
        layout.addWidget(splitter)

        self.sidebar = Sidebar(main_window=self)
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
        self.vcu_graph_panel = VCUGraphPanel(self)
        self.main_display_stack = QStackedWidget()
        self.main_display_stack.addWidget(self.GPSDisplay)
        self.main_display_stack.addWidget(self.vcu_graph_panel)
        content_layout.addWidget(self.main_display_stack)

        self.GPSDisplay.display_mode_changed.connect(self.handle_display_mode_changed)
        self.vcu_status_widget = VCUStatusWidget(self)
        self.vcu_telemetry_updated.connect(self.vcu_graph_panel.update_from_payload)
        self.vcu_telemetry_updated.connect(self.vcu_status_widget.set_data)
        self.GPSDisplay.playback_position_changed.connect(self.handle_playback_position_changed)
        self.GPSDisplay.playback_range_changed.connect(self.handle_playback_range_changed)

        self.playbackButton = QPushButton("play")
        self.playbackButton.clicked.connect(self.start_playback)
        self.pausePlaybackButton = QPushButton("pause")
        self.pausePlaybackButton.clicked.connect(self.pause_playback)
        self.restartPlaybackButton = QPushButton("restart")
        self.restartPlaybackButton.clicked.connect(self.restart_from_selected_file)
        self.buttonContent = QWidget()
        self.buttonContent.setMaximumHeight(50)
        playbackLayout = QHBoxLayout(self.buttonContent)
        playbackLayout.addWidget(self.playbackButton)
        playbackLayout.addWidget(self.pausePlaybackButton)
        playbackLayout.addWidget(self.restartPlaybackButton)
        content_layout.addWidget(self.buttonContent)

        self.timelineContent = QWidget()
        timelineLayout = QHBoxLayout(self.timelineContent)
        timelineLayout.setContentsMargins(0, 0, 0, 0)
        timelineLayout.setSpacing(8)

        self.timelineCurrentLabel = QLabel("00:00")
        self.timelineTotalLabel = QLabel("00:00")
        self.timelineSlider = QSlider(Qt.Horizontal)
        self.timelineSlider.setEnabled(False)
        self.timelineSlider.setRange(0, 0)

        self.timelineSlider.sliderPressed.connect(self.handle_timeline_slider_pressed)
        self.timelineSlider.sliderReleased.connect(self.handle_timeline_slider_released)
        self.timelineSlider.sliderMoved.connect(self.handle_timeline_slider_moved)

        timelineLayout.addWidget(self.timelineCurrentLabel)
        timelineLayout.addWidget(self.timelineSlider)
        timelineLayout.addWidget(self.timelineTotalLabel)
        content_layout.addWidget(self.timelineContent)

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
        self.telemetry_stack = QStackedWidget()
        self.telemetry_stack.addWidget(self.speedometer)
        self.telemetry_stack.addWidget(self.vcu_status_widget)
        self.telemetry_stack.setCurrentWidget(self.speedometer)
        rightSideSlider.setFixedWidth(350)
        rightSideSlider.addWidget(self.telemetry_stack)

        self.acceleration_chart = AccelerationChart(self.GPSDisplay)
        self.GPSDisplay.output_acceleration.connect(self.acceleration_chart.add_acceleration)
        rightSideSlider.addWidget(self.acceleration_chart)
        rightSideSlider.setStretchFactor(0, 2)
        rightSideSlider.setStretchFactor(1, 2)
        rightSideSlider.setSizes([320, 280])
        splitter.addWidget(rightSideSlider)

    def set_source_mode(self, mode):
        if hasattr(self.sidebar, "set_source_mode"):
            self.sidebar.set_source_mode(mode)
        self.handle_type_selected(mode)

    def handle_type_selected(self, mode):
        print(f"MainWindow opperating using: {mode} mode")
        self.sourceType = mode
        if mode == "Bluetooth":
            self.handle_display_mode_changed("map")

    def handle_display_mode_changed(self, mode):
        self.current_display_mode = mode
        if mode == "vcu":
            self.main_display_stack.setCurrentWidget(self.vcu_graph_panel)
            self.telemetry_stack.setCurrentWidget(self.vcu_status_widget)
            self.vcu_graph_panel.rebuild_from_datapoints(
                self.GPSDisplay.data,
                self.GPSDisplay.get_current_index()
            )
            self.vcu_status_widget.rebuild_from_datapoints(
                self.GPSDisplay.data,
                self.GPSDisplay.get_current_index()
            )
            self.acceleration_chart.rebuild_from_datapoints(
                self.GPSDisplay.data,
                self.GPSDisplay.get_current_index()
            )
            return

        self.main_display_stack.setCurrentWidget(self.GPSDisplay)
        self.telemetry_stack.setCurrentWidget(self.speedometer)
        self.vcu_status_widget.clear_data()
        self.acceleration_chart.rebuild_from_datapoints(
            self.GPSDisplay.data,
            self.GPSDisplay.get_current_index()
        )

    def handle_file_selected(self, path):
        print(f"MainWindow loaded file: {path}")
        self.loaded_file_path = path
        self.set_source_mode("File")
        if self.sourceType == "File":
            self.reload_selected_file(path)

    def start_playback(self):
        self.is_playing = True
        self.playback.emit(True)

    def pause_playback(self):
        self.is_playing = False
        self.playback.emit(False)

    def _clear_for_file_reload(self):
        self.pause_playback()
        self.slider_is_scrubbing = False
        self.resume_after_scrub = False

        self.GPSDisplay.clear_loaded_state()
        self.vcu_graph_panel.clear_data()
        self.speedometer.reset_state()
        self.acceleration_chart.clear_data()
        self.vcu_status_widget.clear_data()

        self.updating_timeline_ui = True
        self.timelineSlider.setEnabled(False)
        self.timelineSlider.setRange(0, 0)
        self.timelineSlider.setValue(0)
        self.timelineCurrentLabel.setText("00:00")
        self.timelineTotalLabel.setText("00:00")
        self.updating_timeline_ui = False

    def reload_selected_file(self, path):
        if not path:
            self.text_console.log_message("No file selected to load.", level="WARN")
            return

        self._clear_for_file_reload()
        self.gps_updated.emit(path)

    def restart_from_selected_file(self):
        self.reload_selected_file(self.loaded_file_path)

    def _format_time_label(self, ms):
        total_seconds = max(0, int(ms) // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def handle_playback_range_changed(self, max_index, total_time_ms):
        self.updating_timeline_ui = True
        self.timelineSlider.setEnabled(max_index > 0)
        self.timelineSlider.setRange(0, max_index)
        self.timelineSlider.setValue(0)
        self.timelineCurrentLabel.setText("00:00")
        self.timelineTotalLabel.setText(self._format_time_label(total_time_ms))
        self.updating_timeline_ui = False

    def handle_playback_position_changed(self, current_index, current_time_ms, total_time_ms):
        self.timelineCurrentLabel.setText(self._format_time_label(current_time_ms))
        self.timelineTotalLabel.setText(self._format_time_label(total_time_ms))

        if self.slider_is_scrubbing:
            return

        self.updating_timeline_ui = True
        self.timelineSlider.setValue(current_index)
        self.updating_timeline_ui = False

    def handle_timeline_slider_pressed(self):
        self.slider_is_scrubbing = True
        self.resume_after_scrub = self.is_playing
        if self.is_playing:
            self.pause_playback()

    def handle_timeline_slider_moved(self, index):
        if self.updating_timeline_ui:
            return

        self.GPSDisplay.seek_to_index(index)
        self.vcu_graph_panel.rebuild_from_datapoints(self.GPSDisplay.data, index)
        self.vcu_status_widget.rebuild_from_datapoints(self.GPSDisplay.data, index)
        self.acceleration_chart.rebuild_from_datapoints(self.GPSDisplay.data, index)

    def handle_timeline_slider_released(self):
        self.slider_is_scrubbing = False
        index = self.timelineSlider.value()
        self.GPSDisplay.seek_to_index(index)
        self.vcu_graph_panel.rebuild_from_datapoints(self.GPSDisplay.data, index)
        self.vcu_status_widget.rebuild_from_datapoints(self.GPSDisplay.data, index)
        self.acceleration_chart.rebuild_from_datapoints(self.GPSDisplay.data, index)

        if self.resume_after_scrub:
            self.start_playback()
        self.resume_after_scrub = False

def emit_GPS_pos_from_file(window):
    window.gps_updated.emit(window.loaded_file_path)

async def async_update_GPS_pos(window):
    # Legacy no-op: file reload is now handled immediately in handle_file_selected.
    return

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

                gps_data = await data_getter.read_gps_status(logger=window.text_console)
                imu_data = await data_getter.read_imu_data(logger=window.text_console)
                now_s = asyncio.get_running_loop().time()

                window.text_console.log_message(
                    f"RAW GPS payload: {gps_data}",
                    level="DEBUG"
                )
                window.text_console.log_message(
                    f"RAW IMU payload: {imu_data}",
                    level="DEBUG"
                )

                if imu_data is not None or gps_data is not None:
                    live_point = {}

                    # IMU contributes orientation and acceleration only
                    if imu_data is not None:
                        live_point.update({
                            "yaw":   imu_data["yaw"],
                            "pitch": imu_data["pitch"],
                            "roll":  imu_data["roll"],
                            "ax":    imu_data["ax"],
                            "ay":    imu_data["ay"],
                            "az":    imu_data["az"],
                        })

                    # GPS contributes position and velocity
                    if gps_data is not None:
                        lat = gps_data["lat"]
                        lon = gps_data["lon"]
                        live_point["lat"] = lat
                        live_point["lon"] = lon

                        if prev_gps_sample is not None:
                            dt = now_s - prev_gps_sample["t"]
                            if dt > 0:
                                prev_lat = prev_gps_sample["lat"]
                                prev_lon = prev_gps_sample["lon"]
                                meters_per_deg_lat = 111_320.0
                                meters_per_deg_lon = 111_320.0 * math.cos(
                                    math.radians((lat + prev_lat) / 2.0)
                                )
                                vx = (lon - prev_lon) * meters_per_deg_lon / dt
                                vy = (lat - prev_lat) * meters_per_deg_lat / dt
                                live_point["vx"] = vx
                                live_point["vy"] = vy
                                if prev_gps_velocity is not None:
                                    live_point["ax_w"] = (vx - prev_gps_velocity["vx"]) / dt
                                    live_point["ay_w"] = (vy - prev_gps_velocity["vy"]) / dt
                                prev_gps_velocity = {"vx": vx, "vy": vy}
                            else:
                                live_point["vx"] = 0.0
                                live_point["vy"] = 0.0
                        else:
                            live_point["vx"] = 0.0
                            live_point["vy"] = 0.0
                            prev_gps_velocity = None

                        prev_gps_sample = {"lat": lat, "lon": lon, "t": now_s}

                    speed = math.sqrt(
                        live_point.get("vx", 0.0)**2 + live_point.get("vy", 0.0)**2
                    )
                    source = (
                        "IMU+GPS" if (imu_data is not None and gps_data is not None)
                        else ("IMU" if imu_data is not None else "GPS fallback")
                    )
                    window.text_console.log_message(
                        f"BLE poll complete (source={source}). Speed {speed:.2f} m/s",
                        level="DEBUG"
                    )
                    window.GPSDisplay.load_data_point(live_point)
                    if live_playback_started:
                        window.start_playback()
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
    selected_mode, accepted = QInputDialog.getItem(
        None,
        "Select Startup Mode",
        "Choose the app mode to start in:",
        ["Bluetooth", "File"],
        0,
        False,
    )
    if not accepted:
        selected_mode = "Bluetooth"

    window = MainWindow()
    window.set_source_mode(selected_mode)
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