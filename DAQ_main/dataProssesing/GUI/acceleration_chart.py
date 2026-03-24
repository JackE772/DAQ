from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
class AccelerationChart(QWidget):
    def __init__(self, GPS):
        #TODO setup time var in main window
        self.GPS = GPS #used to get time value
        super().__init__()
        self.acceleration_data = []  # list of (time, acceleration) tuples]
        self.max_acceleration = 0
        self.start_time = -1
        self.end_time = 0
        self.max_height = 90 #%
        self.vert_boarder = 10 #px
        self.horizontal_boarder = 10 #px
        #calc inital height and width
        self.element_width = self.width() - 2 * self.horizontal_boarder
        self.element_height = self.height()*self.max_height/100 - 2 * self.vert_boarder
        self.update()  # trigger initial paint

    def add_acceleration(self, acceleration):
        if(self.start_time == -1):
            self.start_time = self.GPS.get_time()  # get initial time from GPS
        time = self.GPS.get_time()  # get current time from GPS
        self.acceleration_data.append((time, acceleration))
        self.max_acceleration = max(self.max_acceleration, acceleration)
        self.max_acceleration = max(self.max_acceleration, acceleration)
        self.end_time = time
        self.update()  # trigger repaint to show new data

    # Utility function to map a value from one range to another
    def map(self, value, in_min, in_max, out_min, out_max):
        if(in_max - in_min) == 0:
            return out_min  # avoid division by zero
        if(value < in_min):
            return out_min
        return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def paintEvent(self, event):
        if len(self.acceleration_data) < 2:
            return

        if self.end_time <= self.start_time or self.max_acceleration == 0:
            return

        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.fillRect(self.rect(), QColor("#350E0E"))

            pen = QPen(QColor("#FF4444"))
            pen.setWidth(3)
            p.setPen(pen)

            #draw out all points in acceleration data
            last_point = (0, self.height + self.vert_boarder)  # start at bottom left
            for time, acceleration in self.acceleration_data[-30:]:
                x = self.map(time, self.acceleration_data[-30][0], self.end_time, 0, self.width)
                y = self.map(acceleration, 0, self.max_acceleration, self.height + self.vert_boarder, self.vert_boarder)

                p.drawLine(int(last_point[0]), int(last_point[1]), int(x), int(y))
                last_point = (x, y)
            self.draw_axis(p)
        finally:
            p.end()

    def resizeEvent(self, event):
        self.width = event.size().width()
        self.height = event.size().height()*self.max_height/100 - 2 * self.vert_boarder
        self.update()  # trigger repaint on resize

    def draw_axis(self, p):
        #draw x and y axis
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidth(1)
        p.setPen(pen)

        #y axis
        p.drawLine(self.vert_boarder, self.vert_boarder, self.vert_boarder, self.element_height + self.vert_boarder)
        #x axis
        p.drawLine(self.vert_boarder, self.element_height + self.vert_boarder, self.element_width + self.vert_boarder, self.element_height + self.vert_boarder)

        #axis labels
        p.drawText(self.vert_boarder + 5, self.vert_boarder + 15, f"Max Accel: {self.max_acceleration:.2f} m/s²")
        p.drawText(self.element_width - 100, self.element_height + self.vert_boarder - 5, f"Time {self.end_time/1000:.2f} (s)")
