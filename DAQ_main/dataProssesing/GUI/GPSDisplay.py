from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import Qt, QPointF

class GPSWidget(QWidget):
    offset_x = 0
    offset_y = 0
    last_mouse_pos = None

    def __init__(self):
        super().__init__()
        self.points = []   # list of QPointF
        self.startingPoints = [QPointF(1,1), QPointF(100,100), QPointF(200,200), QPointF(300,300)]
        for i in self.startingPoints:
            self.add_point(i.x(), i.y())

    def add_point(self, x, y):
        self.points.append(QPointF(x, y))
        self.update()  # refresh widget

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(QPen(Qt.green, 6))  # 6px dots

        for point in self.points:
            p.drawPoint(point + QPointF(self.offset_x, self.offset_y))

        p.setPen(QPen(Qt.black, 5))  # black border
        p.drawRect(self.rect())  # draw border for reference

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.last_mouse_pos:
            dx = event.x() - self.last_mouse_pos.x()
            dy = event.y() - self.last_mouse_pos.y()

            self.offset_x += dx
            self.offset_y += dy

            self.last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        self.last_mouse_pos = None

    def load_points(self, points_list):
        self.points = [QPointF(x, y) for x, y in points_list]
        self.update()