from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import Qt, QRectF, QPointF
import math

class SpeedometerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.speed = 0  # set from your async BLE loop
        
    def set_speed(self, value):
        self.speed = max(0, min(value, 200))  # clamp
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # center and radius
        r = min(self.width(), self.height()) * 0.45
        cx = self.width() / 2
        cy = self.height() / 2

        # draw arc
        painter.setPen(QPen(QColor("#90E2DD"), 5))
        painter.drawArc(
            QRectF(cx - r, cy - r, 2*r, 2*r),
            225 * 16,  # start at ~225°
            270 * 16   # sweep
        )

        # needle angle (speed mapped to 0–200)
        angle_deg = 225 + (self.speed / 200) * 270
        angle_rad = math.radians(angle_deg)

        # needle
        painter.setPen(QPen(QColor("#E3F8F6"), 6))
        x2 = cx + r * math.cos(angle_rad)
        y2 = cy + r * math.sin(angle_rad)
        painter.drawLine(QPointF(cx, cy), QPointF(x2, y2))

        # text
        painter.setPen(Qt.white)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter, f"{int(self.speed)} km/h")
