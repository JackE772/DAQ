from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout
from vcu_time_charts import VCULineChart

class VCUStatusWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #1a0707;
                border: 1px solid #5b1b1b;
                border-radius: 8px;
            }
            QLabel {
                color: #f4e8e8;
            }
            QProgressBar {
                background-color: #251111;
                border: 1px solid #6a2e2e;
                border-radius: 6px;
                color: #f4e8e8;
                text-align: center;
                min-height: 18px;
            }
            QProgressBar::chunk {
                background-color: #2fa44f;
                border-radius: 4px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("VCU Telemetry")
        title.setStyleSheet("font-weight: 700; color: #9df9c4;")
        layout.addWidget(title)

        self.line_label = QLabel("Line: --")
        self.time_label = QLabel("Time: -- ms")
        self.speed_label = QLabel("Speed: -- mph")
        layout.addWidget(self.line_label)
        layout.addWidget(self.time_label)
        layout.addWidget(self.speed_label)

        self.battery_label = QLabel("Battery")
        layout.addWidget(self.battery_label)

        self.battery_bar = QProgressBar()
        self.battery_bar.setRange(0, 100)
        self.battery_bar.setValue(0)
        self.battery_bar.setFormat("%p%")
        layout.addWidget(self.battery_bar)

        self.battery_trend = VCULineChart("Battery", "%", "#7bd389", self)
        self.battery_trend.max_points = 220
        self.battery_trend.setMinimumHeight(90)
        self._last_battery_time_ms = None
        layout.addWidget(self.battery_trend)

        self._set_battery_chunk_color("#2fa44f")

    def _set_battery_chunk_color(self, color_hex):
        self.battery_bar.setStyleSheet(
            (
                "QProgressBar {"
                " background-color: #251111;"
                " border: 1px solid #6a2e2e;"
                " border-radius: 6px;"
                " color: #f4e8e8;"
                " text-align: center;"
                " min-height: 18px;"
                "}"
                "QProgressBar::chunk {"
                f" background-color: {color_hex};"
                " border-radius: 4px;"
                "}"
            )
        )

    def _apply_battery_style(self, value):
        if value > 50:
            self._set_battery_chunk_color("#2fa44f")
            self.battery_label.setText("Battery (Healthy)")
            return
        if value > 20:
            self._set_battery_chunk_color("#d8a12a")
            self.battery_label.setText("Battery (Low)")
            return

        self._set_battery_chunk_color("#d64545")
        self.battery_label.setText("Battery (Critical)")

    def clear_data(self):
        self.line_label.setText("Line: --")
        self.time_label.setText("Time: -- ms")
        self.speed_label.setText("Speed: -- mph")
        self.battery_label.setText("Battery")
        self.battery_bar.setValue(0)
        self._set_battery_chunk_color("#2fa44f")
        self.battery_trend.clear_data()
        self._last_battery_time_ms = None

    def set_data(self, payload):
        if not payload or not payload.get("is_vcu", False):
            self.clear_data()
            return

        line_number = payload.get("line_number")
        time_ms = payload.get("time_ms")
        speed_mph = payload.get("speed_mph")
        battery_percent = payload.get("battery_percent", 0.0)

        self.line_label.setText(f"Line: {line_number if line_number is not None else '--'}")
        self.time_label.setText(f"Time: {int(time_ms) if time_ms is not None else '--'} ms")
        if speed_mph is None:
            self.speed_label.setText("Speed: -- mph")
        else:
            self.speed_label.setText(f"Speed: {float(speed_mph):.2f} mph")

        value = int(max(0.0, min(100.0, float(battery_percent))))
        self.battery_bar.setValue(value)
        self._apply_battery_style(value)

        # When scrubbing backwards, reset so the trend reflects the selected timeline.
        if time_ms is not None:
            t = float(time_ms)
            if self._last_battery_time_ms is not None and t < self._last_battery_time_ms:
                self.battery_trend.clear_data()
            self._last_battery_time_ms = t

        self.battery_trend.add_sample(time_ms, value)

    def rebuild_from_datapoints(self, data_points, end_index):
        self.clear_data()
        if not data_points:
            return

        last_index = max(0, min(end_index, len(data_points) - 1))
        current_point = data_points[last_index]
        current_time_ms = float(getattr(current_point, "time_ms", current_point.time))
        start_time_ms = current_time_ms - self.battery_trend.window_ms

        self.line_label.setText(f"Line: {getattr(current_point, 'line_number', '--')}")
        self.time_label.setText(f"Time: {int(current_time_ms)} ms")

        speed_mph = getattr(current_point, "speed_mph", None)
        if speed_mph is None:
            self.speed_label.setText("Speed: -- mph")
        else:
            self.speed_label.setText(f"Speed: {float(speed_mph):.2f} mph")

        battery_percent = getattr(current_point, "battery_percent", 0.0)
        value = int(max(0.0, min(100.0, float(battery_percent))))
        self.battery_bar.setValue(value)
        self._apply_battery_style(value)

        for index in range(last_index + 1):
            point = data_points[index]
            if not hasattr(point, "battery_percent"):
                continue

            time_ms = float(getattr(point, "time_ms", point.time))
            if time_ms < start_time_ms:
                continue

            self.battery_trend.add_sample(time_ms, getattr(point, "battery_percent", 0.0))

        self._last_battery_time_ms = current_time_ms
