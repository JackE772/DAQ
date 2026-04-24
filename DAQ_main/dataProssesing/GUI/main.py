#using asyncio for asynchronous programming this is deprecated and included in python
#TODO refacter to avoid using asyncio
import asyncio
import os

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
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QSplitter, QStackedWidget, QSlider, QLabel, QFrame, QSizePolicy
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
        self.bluetooth_review_mode = False
        self.bluetooth_review_buffer = []
        self.max_review_buffer_points = 4000
        self.review_segment_start_index = 0
        self.review_segment_end_index = 0

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.brand_logo_path = self.resolve_brand_logo_path()

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(self.spliter_syle)
        layout.addWidget(splitter)

        self.sidebar = Sidebar(main_window=self, brand_logo_path=self.brand_logo_path)
        self.sidebar.setMinimumWidth(150)
        self.sidebar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
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

        self.playbackButton = QPushButton("Play >")
        self.playbackButton.setObjectName("transportButton")
        self.playbackButton.setToolTip("Resume playback")
        self.playbackButton.clicked.connect(self.start_playback)
        self.pausePlaybackButton = QPushButton("Pause ||")
        self.pausePlaybackButton.setObjectName("transportButton")
        self.pausePlaybackButton.setToolTip("Pause playback (enters review mode in Bluetooth)")
        self.pausePlaybackButton.clicked.connect(self.pause_playback)
        self.restartPlaybackButton = QPushButton("Reset")
        self.restartPlaybackButton.setObjectName("transportButton")
        self.restartPlaybackButton.setToolTip("Reload selected file")
        self.restartPlaybackButton.clicked.connect(self.restart_from_selected_file)
        self.returnLiveButton = QPushButton("Live View")
        self.returnLiveButton.setObjectName("transportButton")
        self.returnLiveButton.setToolTip("Return to live Bluetooth stream")
        self.returnLiveButton.clicked.connect(self.return_to_live_view)
        self.returnLiveButton.setVisible(False)
        self.buttonContent = QFrame()
        self.buttonContent.setObjectName("transportBar")
        self.buttonContent.setMaximumHeight(58)
        playbackLayout = QHBoxLayout(self.buttonContent)
        playbackLayout.setContentsMargins(10, 8, 10, 8)
        playbackLayout.setSpacing(8)

        self.liveStatusBadge = QLabel("LIVE")
        self.liveStatusBadge.setObjectName("liveStatusBadge")

        playbackLayout.addWidget(self.liveStatusBadge)
        playbackLayout.addWidget(self.playbackButton)
        playbackLayout.addWidget(self.pausePlaybackButton)
        playbackLayout.addWidget(self.restartPlaybackButton)
        playbackLayout.addWidget(self.returnLiveButton)
        playbackLayout.addStretch(1)
        content_layout.addWidget(self.buttonContent)

        self.timelineContent = QFrame()
        self.timelineContent.setObjectName("timelineBar")
        timelineLayout = QHBoxLayout(self.timelineContent)
        timelineLayout.setContentsMargins(10, 8, 10, 8)
        timelineLayout.setSpacing(10)

        self.timelineCurrentLabel = QLabel("00:00")
        self.timelineCurrentLabel.setObjectName("timelineLabel")
        self.timelineTotalLabel = QLabel("00:00")
        self.timelineTotalLabel.setObjectName("timelineLabel")
        self.timelineSlider = QSlider(Qt.Horizontal)
        self.timelineSlider.setObjectName("timelineSlider")
        self.timelineSlider.setEnabled(False)
        self.timelineSlider.setRange(0, 0)

        self.timelineSlider.sliderPressed.connect(self.handle_timeline_slider_pressed)
        self.timelineSlider.sliderReleased.connect(self.handle_timeline_slider_released)
        self.timelineSlider.sliderMoved.connect(self.handle_timeline_slider_moved)

        timelineLayout.addWidget(self.timelineCurrentLabel)
        timelineLayout.addWidget(self.timelineSlider)
        timelineLayout.addWidget(self.timelineTotalLabel)
        content_layout.addWidget(self.timelineContent)

        self.apply_transport_styles()
        self.set_live_status("LIVE")

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
        rightSideSlider.setMinimumWidth(150)
        rightSideSlider.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        rightSideSlider.addWidget(self.telemetry_stack)

        self.acceleration_chart = AccelerationChart(self.GPSDisplay)
        self.GPSDisplay.output_acceleration.connect(self.acceleration_chart.add_acceleration)
        rightSideSlider.addWidget(self.acceleration_chart)
        rightSideSlider.setStretchFactor(0, 2)
        rightSideSlider.setStretchFactor(1, 2)
        rightSideSlider.setSizes([320, 280])
        splitter.addWidget(rightSideSlider)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([168, 280, 168])

        self.apply_theme_styles()

    def set_source_mode(self, mode):
        if hasattr(self.sidebar, "set_source_mode"):
            self.sidebar.set_source_mode(mode)
        self.handle_type_selected(mode)

    def handle_type_selected(self, mode):
        print(f"MainWindow opperating using: {mode} mode")
        self.sourceType = mode
        self.bluetooth_review_mode = False
        self.bluetooth_review_buffer.clear()
        self.review_segment_start_index = 0
        self.review_segment_end_index = 0
        self.returnLiveButton.setVisible(False)
        if mode == "Bluetooth":
            self.set_live_status("LIVE")
            self.handle_display_mode_changed("map")
        else:
            self.set_live_status("FILE")

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
        if self.sourceType == "Bluetooth" and not self.bluetooth_review_mode:
            self.set_live_status("LIVE")
        elif self.sourceType == "File":
            self.set_live_status("FILE")

    def pause_playback(self):
        self.is_playing = False
        self.playback.emit(False)

        if self.sourceType == "Bluetooth" and not self.bluetooth_review_mode:
            self.bluetooth_review_mode = True
            self.bluetooth_review_buffer.clear()
            self.review_segment_start_index = 0
            self.review_segment_end_index = max(0, self.GPSDisplay.get_data_length() - 1)
            self.returnLiveButton.setVisible(True)
            self.set_live_status("REVIEW")
            self.refresh_review_timeline_bounds()
            self.text_console.log_message(
                "Bluetooth paused. Entered review mode; live samples buffered."
            )
        elif self.sourceType == "File":
            self.set_live_status("FILE")

    def is_bluetooth_review_mode(self):
        return self.sourceType == "Bluetooth" and self.bluetooth_review_mode

    def handle_live_point(self, point):
        if self.is_bluetooth_review_mode():
            self.bluetooth_review_buffer.append(point)
            if len(self.bluetooth_review_buffer) > self.max_review_buffer_points:
                self.bluetooth_review_buffer = self.bluetooth_review_buffer[-self.max_review_buffer_points:]
            return

        self.GPSDisplay.load_data_point(point)
        if self.sourceType == "Bluetooth":
            self.refresh_live_timeline_bounds()

    def refresh_live_timeline_bounds(self):
        if self.sourceType != "Bluetooth" or self.bluetooth_review_mode:
            return

        max_index = max(0, self.GPSDisplay.get_data_length() - 1)
        self.updating_timeline_ui = True
        self.timelineSlider.setEnabled(max_index > 0)
        self.timelineSlider.setRange(0, max_index)
        self.timelineTotalLabel.setText(self._format_time_label(self.GPSDisplay.get_total_time_ms()))
        self.updating_timeline_ui = False

    def refresh_review_timeline_bounds(self):
        if self.sourceType != "Bluetooth" or not self.bluetooth_review_mode:
            return

        self.review_segment_end_index = max(0, self.GPSDisplay.get_data_length() - 1)
        self.updating_timeline_ui = True
        self.timelineSlider.setEnabled(self.review_segment_end_index > 0)
        self.timelineSlider.setRange(self.review_segment_start_index, self.review_segment_end_index)
        self.timelineTotalLabel.setText(self._format_time_label(self.GPSDisplay.get_total_time_ms()))
        self.updating_timeline_ui = False

    def return_to_live_view(self):
        if not self.is_bluetooth_review_mode():
            return

        if self.bluetooth_review_buffer:
            for point in self.bluetooth_review_buffer:
                self.GPSDisplay.load_data_point(point, emit_update=False)

        live_index = self.GPSDisplay.get_data_length() - 1
        if live_index >= 0:
            self.GPSDisplay.seek_to_index(live_index)

        self.bluetooth_review_buffer.clear()
        self.bluetooth_review_mode = False
        self.returnLiveButton.setVisible(False)
        self.set_live_status("LIVE")
        self.refresh_live_timeline_bounds()
        self.start_playback()
        self.text_console.log_message("Returned to live Bluetooth view.", level="SUCCESS")

    def _clear_for_file_reload(self):
        self.pause_playback()
        self.slider_is_scrubbing = False
        self.resume_after_scrub = False
        self.bluetooth_review_mode = False
        self.bluetooth_review_buffer.clear()
        self.returnLiveButton.setVisible(False)
        if self.sourceType == "Bluetooth":
            self.set_live_status("LIVE")
        else:
            self.set_live_status("FILE")

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
        if self.sourceType == "Bluetooth" and self.bluetooth_review_mode:
            if self.GPSDisplay.get_data_length() == 0:
                return

            self.GPSDisplay.seek_to_index(self.review_segment_start_index)
            self.vcu_graph_panel.rebuild_from_datapoints(self.GPSDisplay.data, self.review_segment_start_index)
            self.vcu_status_widget.rebuild_from_datapoints(self.GPSDisplay.data, self.review_segment_start_index)
            self.acceleration_chart.rebuild_from_datapoints(self.GPSDisplay.data, self.review_segment_start_index)
            self.timelineSlider.setValue(self.review_segment_start_index)
            return

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

    def resolve_brand_logo_path(self):
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_dir = os.path.abspath(os.path.join(gui_dir, "..", "..", ".."))
        candidates = [
            os.path.join(gui_dir, "assets", "ae_logo.png"),
            os.path.join(gui_dir, "assets", "logo.png"),
            os.path.join(workspace_dir, "assets", "ae_logo.png"),
            os.path.join(workspace_dir, "assets", "logo.png"),
            os.path.join(workspace_dir, "ae_logo.png"),
            os.path.join(workspace_dir, "logo.png"),
        ]

        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def set_live_status(self, mode):
        if mode == "REVIEW":
            self.liveStatusBadge.setText("REVIEW")
            self.liveStatusBadge.setStyleSheet(
                "background-color: #4c1d1d; color: #ffd6d6; border: 1px solid #b94a4a; border-radius: 11px;"
                "padding: 2px 10px; font-weight: 700;"
            )
            return

        if mode == "FILE":
            self.liveStatusBadge.setText("FILE")
            self.liveStatusBadge.setStyleSheet(
                "background-color: #232f3a; color: #dce8f5; border: 1px solid #47637d; border-radius: 11px;"
                "padding: 2px 10px; font-weight: 700;"
            )
            return

        self.liveStatusBadge.setText("LIVE")
        self.liveStatusBadge.setStyleSheet(
            "background-color: #113823; color: #bcffd7; border: 1px solid #2fa44f; border-radius: 11px;"
            "padding: 2px 10px; font-weight: 700;"
        )

    def apply_transport_styles(self):
        self.timelineContent.setStyleSheet(
            "QFrame#timelineBar {"
            " background-color: #1a0707;"
            " border: 1px solid #5b1b1b;"
            " border-radius: 8px;"
            "}"
            "QLabel#timelineLabel {"
            " color: #f4e8e8;"
            " font-weight: 600;"
            " min-width: 44px;"
            "}"
            "QSlider#timelineSlider::groove:horizontal {"
            " background: #2b1212;"
            " border: 1px solid #6a2e2e;"
            " height: 8px;"
            " border-radius: 4px;"
            "}"
            "QSlider#timelineSlider::sub-page:horizontal {"
            " background: #c04f4f;"
            " border-radius: 4px;"
            "}"
            "QSlider#timelineSlider::add-page:horizontal {"
            " background: #2b1212;"
            " border-radius: 4px;"
            "}"
            "QSlider#timelineSlider::handle:horizontal {"
            " background: #f4e8e8;"
            " border: 1px solid #7d3a3a;"
            " width: 14px;"
            " margin: -5px 0;"
            " border-radius: 7px;"
            "}"
            "QSlider#timelineSlider::handle:horizontal:hover {"
            " background: #ffffff;"
            "}"
        )

    def apply_theme_styles(self):
        self.centralWidget().setStyleSheet(
            "QWidget {"
            f" background-color: {background};"
            " color: #f4e8e8;"
            "}"
            "QFrame#transportBar, QFrame#timelineBar, QFrame#sidebarBrandBanner {"
            " background-color: #1a0707;"
            " border: 1px solid #5b1b1b;"
            " border-radius: 8px;"
            "}"
            "QPushButton {"
            " background-color: #251111;"
            " color: #f4e8e8;"
            " border: 1px solid #6a2e2e;"
            " border-radius: 6px;"
            " padding: 7px 14px;"
            " font-weight: 600;"
            "}"
            "QPushButton:hover {"
            " background-color: #321616;"
            " border: 1px solid #8e3f3f;"
            "}"
            "QPushButton:pressed {"
            " background-color: #140808;"
            "}"
            "QPushButton:disabled {"
            " background-color: #1c1010;"
            " color: #7f6767;"
            " border: 1px solid #3f2424;"
            "}"
            "QComboBox, QTextEdit {"
            " background-color: #120707;"
            " color: #f4e8e8;"
            " border: 1px solid #6a2e2e;"
            " border-radius: 6px;"
            " padding: 5px;"
            " selection-background-color: #c04f4f;"
            "}"
            "QComboBox::drop-down {"
            " border: none;"
            " width: 22px;"
            "}"
            "QSlider::groove:horizontal {"
            " background: #2b1212;"
            " border: 1px solid #6a2e2e;"
            " height: 8px;"
            " border-radius: 4px;"
            "}"
            "QSlider::sub-page:horizontal {"
            " background: #c04f4f;"
            " border-radius: 4px;"
            "}"
            "QSlider::add-page:horizontal {"
            " background: #2b1212;"
            " border-radius: 4px;"
            "}"
            "QSlider::handle:horizontal {"
            " background: #f4e8e8;"
            " border: 1px solid #7d3a3a;"
            " width: 14px;"
            " margin: -5px 0;"
            " border-radius: 7px;"
            "}"
            "QSlider::handle:horizontal:hover {"
            " background: #ffffff;"
            "}"
            "QLabel#liveStatusBadge {"
            " background-color: #113823;"
            " color: #bcffd7;"
            " border: 1px solid #2fa44f;"
            " border-radius: 11px;"
            " padding: 2px 10px;"
            " font-weight: 700;"
            "}"
        )

def emit_GPS_pos_from_file(window):
    window.gps_updated.emit(window.loaded_file_path)

async def async_update_GPS_pos(window):
    # Legacy no-op: file reload is now handled immediately in handle_file_selected.
    return

async def async_ble_loop(window):
    data_getter = DataGetter()
    window.ble_data_getter = data_getter
    window.text_console.log_message("BLE loop started. Waiting for Bluetooth mode.", level="INFO")
    reconnect_delay_seconds = 2.0
    imu_accel_scale = 1.0
    imu_accel_deadband = 0.03
    imu_velocity_floor = 0.05
    live_playback_started = False
    last_mode = None
    prev_imu_sample_t = None
    imu_speed_estimate = 0.0

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
                    prev_imu_sample_t = None
                    imu_speed_estimate = 0.0
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
                    imu_speed_sample = None

                    # IMU contributes orientation and acceleration only
                    if imu_data is not None:
                        raw_ax = float(imu_data["ax"])
                        ax_for_integration = raw_ax * imu_accel_scale
                        if abs(ax_for_integration) < imu_accel_deadband:
                            ax_for_integration = 0.0

                        live_point.update({
                            "yaw":   imu_data["yaw"],
                            "pitch": imu_data["pitch"],
                            "roll":  imu_data["roll"],
                            "ax_raw": raw_ax,
                            "ax":    ax_for_integration,
                            "ay":    imu_data["ay"],
                            "az":    imu_data["az"],
                        })

                        if prev_imu_sample_t is not None:
                            imu_dt = now_s - prev_imu_sample_t
                            if imu_dt > 0:
                                imu_speed_estimate = max(0.0, imu_speed_estimate + ax_for_integration * imu_dt)
                                if imu_speed_estimate < imu_velocity_floor:
                                    imu_speed_estimate = 0.0
                                imu_speed_sample = imu_speed_estimate
                        prev_imu_sample_t = now_s

                        # Prefer IMU integrated speed for live telemetry when IMU exists.
                        live_point["speed"] = imu_speed_sample if imu_speed_sample is not None else imu_speed_estimate

                    # GPS contributes position and velocity
                    if gps_data is not None:
                        lat = gps_data["lat"]
                        lon = gps_data["lon"]
                        gps_speed = float(gps_data.get("speed", 0.0))
                        live_point["lat"] = lat
                        live_point["lon"] = lon
                        live_point["speed"] = gps_speed
                    elif imu_speed_sample is not None:
                        live_point["speed"] = imu_speed_sample
                        live_point["x"] = 0.0
                        live_point["y"] = 0.0

                    speed = live_point.get("speed")
                    source = (
                        "IMU+GPS" if (imu_data is not None and gps_data is not None)
                        else ("IMU" if imu_data is not None else "GPS fallback")
                    )
                    window.text_console.log_message(
                        f"BLE poll complete (source={source}). Speed {speed:.2f} m/s",
                        level="DEBUG"
                    )
                    window.handle_live_point(live_point)
                    if live_playback_started and not window.is_bluetooth_review_mode():
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
                prev_imu_sample_t = None
                imu_speed_estimate = 0.0
                window.text_console.log_message(
                    f"Connection lost. Reconnecting in {reconnect_delay_seconds:.1f}s",
                    level="WARN"
                )
                await asyncio.sleep(reconnect_delay_seconds)
                continue

            await asyncio.sleep(0.1)  # poll every 0.1 seconds
    finally:
        await data_getter.disconnect(logger=window.text_console)
        window.ble_data_getter = None

def main():
    app = QApplication(sys.argv)
    selected_mode = "Bluetooth"

    window = MainWindow()
    window.set_source_mode(selected_mode)
    window.showMaximized()

    # Integrate asyncio loop with Qt
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    app.aboutToQuit.connect(loop.stop)

    ble_task = loop.create_task(async_ble_loop(window))
    file_task = loop.create_task(async_update_GPS_pos(window))

    with loop:
        try:
            loop.run_forever()
        finally:
            for task in (ble_task, file_task):
                if not task.done():
                    task.cancel()
            loop.run_until_complete(asyncio.gather(ble_task, file_task, return_exceptions=True))

if __name__ == "__main__":
    main()