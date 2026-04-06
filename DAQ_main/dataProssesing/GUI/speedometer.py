from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt, QRectF, QPointF
import math

class SpeedometerWidget(QWidget):
    def __init__(self, GPS, main_window):
        super().__init__()
        self.true_speed = 0.0
        self.needle_speed = 0.0
        self.speed_lim = 50
        self.GPS = GPS
        self.GPS.output_speed.connect(self.set_speed)
        self.max_speed_true = 0.0
        self.speed_log = []

        self.main_window = main_window


    def set_speed(self, value):
        self.true_speed = max(0.0, float(value))
        self.needle_speed = max(0.0, min(self.true_speed, self.speed_lim))
        self.speed_log.append(self.true_speed)

        if len(self.speed_log) > 20:
            self.speed_log.pop(0)

        self.max_speed_true = max(self.speed_log)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        r = min(self.width(), self.height()) * 0.42
        cx = self.width() / 2
        cy = self.height() / 2
        dial_rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)

        painter.fillRect(self.rect(), QColor("#0f0a0a"))

        # Base arc.
        painter.setPen(QPen(QColor("#401717"), 6, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(dial_rect, 135 * 16, -90 * 16)

        # Max reached arc (capped).
        max_for_arc = min(self.max_speed_true, self.speed_lim)
        max_angle = (max_for_arc / self.speed_lim) * 90.0
        painter.setPen(QPen(QColor("#d9362a"), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(dial_rect, 135 * 16, -max_angle * 16)

        # Sparse major ticks for a cleaner dial.
        for i in range(0, self.speed_lim + 1, 10):
            frac = i / self.speed_lim
            angle_deg = 225 - frac * 90
            angle_rad = math.radians(angle_deg)
            outer_x = cx + r * math.cos(angle_rad)
            outer_y = cy - r * math.sin(angle_rad)
            tick_len = r * 0.10
            inner_x = cx + (r - tick_len) * math.cos(angle_rad)
            inner_y = cy - (r - tick_len) * math.sin(angle_rad)
            painter.setPen(QPen(QColor("#8a3a3a"), 2))
            painter.drawLine(QPointF(inner_x, inner_y), QPointF(outer_x, outer_y))

        # Needle (capped by speed limit).
        angle_deg = 225 - (self.needle_speed / self.speed_lim) * 90
        angle_rad = math.radians(angle_deg)
        tip_x = cx + (r * 0.84) * math.cos(angle_rad)
        tip_y = cy - (r * 0.84) * math.sin(angle_rad)
        painter.setPen(QPen(QColor("#f2f2f2"), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(cx, cy), QPointF(tip_x, tip_y))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#b82d24"))
        painter.drawEllipse(QPointF(cx, cy), r * 0.06, r * 0.06)

        # True speed text (never clamped).
        painter.setPen(QColor("#f4e8e8"))
        speed_font = QFont(self.font())
        speed_font.setPointSize(max(10, int(r * 0.14)))
        speed_font.setBold(True)
        painter.setFont(speed_font)
        painter.drawText(self.rect().adjusted(0, int(r * 0.12), 0, 0), Qt.AlignHCenter, f"{self.true_speed:.1f} m/s")

        painter.setPen(QColor("#ab8f8f"))
        meta_font = QFont(self.font())
        meta_font.setPointSize(max(8, int(r * 0.07)))
        painter.setFont(meta_font)
        painter.drawText(
            self.rect().adjusted(0, int(r * 0.33), 0, 0),
            Qt.AlignHCenter,
            f"needle max {self.speed_lim} | peak {self.max_speed_true:.1f}"
        )
