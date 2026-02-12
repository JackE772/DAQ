from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import Qt, QRectF, QPointF
import math

class SpeedometerWidget(QWidget):
    def __init__(self, GPS, main_window):
        super().__init__()
        self.speed = 0  # set from your async BLE loop
        self.speed_lim = 50 #max speed the needle can dispaly
        self.GPS = GPS
        self.GPS.output_speed.connect(self.set_speed)
        self.max_speed = self.speed
        self.speed_log = []

        self.main_window = main_window


    def set_speed(self, value):
        self.speed = max(0, min(value, self.speed_lim))  # clamp
        self.speed_log.append(self.speed)

        if len(self.speed_log) > 20:  # keep last 100 speeds
            self.speed_log.pop(0)

        self.max_speed = max(self.speed_log)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # center and radius
        r = min(self.width(), self.height()) * 0.45
        cx = self.width() / 2
        cy = self.height() / 2

        # draw arc
        painter.setPen(QPen(QColor("#990000"), 5))
        painter.drawArc(
            QRectF(cx - r, cy - r, 2*r, 2*r),
            45 * 16,  # start at ~225°
            90 * 16   # sweep
        )

        # draw arc showing max speed
        max_angle = (self.max_speed / self.speed_lim) * 90
        painter.setPen(QPen(QColor("#FF9999"), 5))
        painter.drawArc(
            QRectF((cx - r), (cy - r), 2*r, 2*r),
            135 * 16,  # start at ~225°
            -max_angle * 16   # sweep
        )

        # needle angle (speed mapped to 0–speed lim)
        angle_deg = 225 + (self.speed / self.speed_lim) * 90
        angle_rad = math.radians(angle_deg)

        # needle
        painter.setPen(QPen(QColor("#FFFFFF"), 6))
        x2 = cx + r * math.cos(angle_rad)
        y2 = cy + r * math.sin(angle_rad)
        painter.drawLine(QPointF(cx, cy), QPointF(x2, y2))

        # text
        painter.setPen(Qt.white)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter, f"{int(self.speed)} m/h")
