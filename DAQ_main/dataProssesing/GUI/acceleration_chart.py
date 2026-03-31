from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt
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
        self.left_margin = 45 #px for Y-axis labels
        self.bottom_margin = 20 #px for X-axis labels
        #calc inital height and width
        self.horizontal_boarder = 10 #px
        self.element_width = self.width() - 2 * self.horizontal_boarder
        self.element_height = self.height()*self.max_height/100 - 2 * self.vert_boarder
        self.update()  # trigger initial paint

    def add_acceleration(self, acceleration):
        if(self.start_time == -1):
            self.start_time = self.GPS.get_time()  # get initial time from GPS
        time = self.GPS.get_time()  # get current time from GPS
        self.acceleration_data.append((time, acceleration))
        speeds, accelerations = zip(*self.acceleration_data)
        self.max_acceleration = max(accelerations[-30:])
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

            # Calculate chart area (accounting for margins)
            chart_left = self.left_margin
            chart_width = self.width - self.left_margin
            chart_top = self.vert_boarder
            chart_bottom = self.height + self.vert_boarder - self.bottom_margin
            chart_height = chart_bottom - chart_top

            pen = QPen(QColor("#FF4444"))
            pen.setWidth(3)
            p.setPen(pen)

            #draw out all points in acceleration data
            last_point = (chart_left, chart_bottom)  # start at bottom left
            for time, acceleration in self.acceleration_data[-30:]:
                x = self.map(time, self.acceleration_data[-30][0], self.end_time, chart_left, chart_left + chart_width)
                y = self.map(acceleration, 0, self.max_acceleration, chart_bottom, chart_top)

                p.drawLine(int(last_point[0]), int(last_point[1]), int(x), int(y))
                last_point = (x, y)
            
            # Draw scale labels
            self.draw_scale_labels(p, chart_left, chart_top, chart_bottom, chart_width, chart_height)
                
        finally:
            p.end()

    def draw_scale_labels(self, p, chart_left, chart_top, chart_bottom, chart_width, chart_height):
        """Draw Y-axis (acceleration) and X-axis (time) scale labels"""
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidth(1)
        p.setPen(pen)
        
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        
        # Draw Y-axis labels (acceleration scale) - divide into 5 parts
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            accel_val = self.max_acceleration * i / num_y_ticks
            y = self.map(accel_val, 0, self.max_acceleration, chart_bottom, chart_top)
            # Draw tick mark
            p.drawLine(int(chart_left - 5), int(y), int(chart_left), int(y))
            # Draw label
            label = f"{accel_val:.2f}"
            p.drawText(5, int(y + 4), label)
        
        # Draw Y-axis title
        p.save()
        p.translate(12, chart_top + chart_height / 2)
        p.rotate(-90)
        p.drawText(0, 0, "m/s²")
        p.restore()
        
        # Draw X-axis labels (time since now, labeled in reverse)
        time_data = self.acceleration_data[-30:]
        if len(time_data) > 0:
            start_time = time_data[0][0]
            time_range = self.end_time - start_time
            
            # Draw time labels showing seconds ago (negative from current)
            num_time_ticks = 5
            for i in range(num_time_ticks + 1):
                # Position from left to right
                x = chart_left + (chart_width * i / num_time_ticks)
                # Draw tick mark
                p.drawLine(int(x), int(chart_bottom), int(x), int(chart_bottom + 5))
                # Time since now (left side is oldest = most negative, right side is now = 0)
                seconds_ago = -time_range * (1 - i / num_time_ticks)
                label = f"{seconds_ago:.1f}s"
                p.drawText(int(x - 15), int(chart_bottom + 15), label)

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
