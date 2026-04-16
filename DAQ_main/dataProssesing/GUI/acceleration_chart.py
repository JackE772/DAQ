from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from vcu_time_charts import VCULineChart


class AccelerationChart(QWidget):
    def __init__(self, GPS):
        self.GPS = GPS
        super().__init__()

        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.chart = VCULineChart("Acceleration", "m/s²", "#FF4444", self)
        self.chart.max_points = 320
        self.chart.setMinimumHeight(180)
        self.chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.chart)

    def add_acceleration(self, acceleration):
        self.chart.add_sample(self.GPS.get_time(), acceleration)

    def clear_data(self):
        self.chart.clear_data()

    def rebuild_from_datapoints(self, data_points, end_index):
        self.chart.clear_data()
        if not data_points:
            return

        last_index = max(0, min(end_index, len(data_points) - 1))
        end_time_ms = float(data_points[last_index].time)
        start_time_ms = end_time_ms - self.chart.window_ms

        for index in range(last_index + 1):
            point = data_points[index]
            if float(point.time) < start_time_ms:
                continue
            self.chart.add_sample(point.time, point.acceleration)
