from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QWidget


class VCULineChart(QWidget):
    def __init__(self, title, unit, line_color, parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.line_color = QColor(line_color)
        self.samples = []
        self.max_points = 320
        self.window_ms = 30_000

    def clear_data(self):
        self.samples.clear()
        self.update()

    def add_sample(self, time_ms, value):
        if time_ms is None or value is None:
            return

        time_value = float(time_ms)
        numeric_value = float(value)

        if self.samples and time_value < self.samples[-1][0]:
            self.samples.clear()

        self.samples.append((time_value, numeric_value))

        cutoff = time_value - self.window_ms
        self.samples = [sample for sample in self.samples if sample[0] >= cutoff]

        if len(self.samples) > self.max_points:
            self.samples = self.samples[-self.max_points:]
        self.update()

    def _map(self, value, in_min, in_max, out_min, out_max):
        if in_max == in_min:
            return out_min
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#350E0E"))

        left = 44
        top = 24
        right = self.width() - 10
        bottom = self.height() - 24

        if right <= left or bottom <= top:
            return

        painter.setPen(QPen(QColor("#6b2b2b"), 1))
        painter.drawRect(left, top, right - left, bottom - top)

        painter.setPen(QColor("#f4e8e8"))
        painter.drawText(10, 16, self.title)

        if len(self.samples) < 2:
            painter.setPen(QColor("#b08f8f"))
            painter.drawText(left + 6, top + 16, "Waiting for data...")
            return

        time_values = [point[0] for point in self.samples]
        y_values = [point[1] for point in self.samples]

        min_time = min(time_values)
        max_time = max(time_values)
        if max_time == min_time:
            max_time += 1.0

        min_y = min(y_values)
        max_y = max(y_values)
        if max_y == min_y:
            max_y += 1.0
            min_y -= 1.0

        path = QPainterPath()
        first_x = self._map(time_values[0], min_time, max_time, left, right)
        first_y = self._map(y_values[0], min_y, max_y, bottom, top)
        path.moveTo(first_x, first_y)

        for t_ms, y in self.samples[1:]:
            x = self._map(t_ms, min_time, max_time, left, right)
            py = self._map(y, min_y, max_y, bottom, top)
            path.lineTo(x, py)

        painter.setPen(QPen(self.line_color, 2))
        painter.drawPath(path)

        painter.setPen(QColor("#b08f8f"))
        painter.drawText(4, top + 4, f"{max_y:.2f}")
        painter.drawText(4, bottom, f"{min_y:.2f}")

        start_s = min_time / 1000.0
        end_s = max_time / 1000.0
        painter.drawText(left, self.height() - 6, f"{start_s:.1f}s")
        painter.drawText(right - 38, self.height() - 6, f"{end_s:.1f}s")

        current_value = y_values[-1]
        painter.setPen(QColor("#f4e8e8"))
        painter.drawText(right - 110, 16, f"{current_value:.2f} {self.unit}")


class VCUGraphPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        self.speed_chart = VCULineChart("Speed", "mph", "#69d2e7")
        self.dc_current_chart = VCULineChart("DC Current", "A", "#f7b32b")
        self.ac_current_chart = VCULineChart("AC Current", "A", "#f45b69")
        self.ac_voltage_chart = VCULineChart("AC Voltage", "V", "#7bd389")

        layout.addWidget(self.speed_chart, 0, 0)
        layout.addWidget(self.dc_current_chart, 0, 1)
        layout.addWidget(self.ac_current_chart, 1, 0)
        layout.addWidget(self.ac_voltage_chart, 1, 1)

    def clear_data(self):
        self.speed_chart.clear_data()
        self.dc_current_chart.clear_data()
        self.ac_current_chart.clear_data()
        self.ac_voltage_chart.clear_data()

    def update_from_payload(self, payload):
        if not payload or not payload.get("is_vcu", False):
            return

        time_ms = payload.get("time_ms")
        self.speed_chart.add_sample(time_ms, payload.get("speed_mph"))
        self.dc_current_chart.add_sample(time_ms, payload.get("dc_current"))
        self.ac_current_chart.add_sample(time_ms, payload.get("ac_current"))
        self.ac_voltage_chart.add_sample(time_ms, payload.get("ac_voltage"))

    def rebuild_from_datapoints(self, data_points, end_index):
        self.clear_data()
        if not data_points:
            return

        last_index = max(0, min(end_index, len(data_points) - 1))
        end_time_ms = float(getattr(data_points[last_index], "time_ms", data_points[last_index].time))
        start_time_ms = end_time_ms - self.speed_chart.window_ms if hasattr(self, "speed_chart") else end_time_ms - 30_000

        for index in range(last_index + 1):
            data_point = data_points[index]
            if not hasattr(data_point, "battery_percent"):
                continue

            time_ms = float(getattr(data_point, "time_ms", data_point.time))
            if time_ms < start_time_ms:
                continue

            payload = {
                "is_vcu": True,
                "time_ms": time_ms,
                "speed_mph": getattr(data_point, "speed_mph", None),
                "dc_current": getattr(data_point, "dc_current", None),
                "ac_current": getattr(data_point, "ac_current", None),
                "ac_voltage": getattr(data_point, "ac_voltage", None),
            }
            self.update_from_payload(payload)
