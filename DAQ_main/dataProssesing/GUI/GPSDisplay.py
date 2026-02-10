from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QPainterPath
from PySide6.QtCore import Qt, QPointF, QTimer, Signal
import csv
import math

class DataPoint():
    latitude = 0
    longitude = 0
    acceleration = 0
    speed = 0
    time = 0
    
    def __init__(self, x, y, s, a, t):
        self.latitude = x
        self.longitude = y
        self.speed = s
        self.acceleration = a
        self.time = t

class GPSWidget(QWidget):
    rows_skiped = 0
    playback = False
    output_speed = Signal(float)

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        #listens to main window for updates
        main_window.gps_updated.connect(self.load_from_file)
        main_window.playback.connect(self.set_playback_status)

        # view state
        self.offset_x = self.width()/2
        self.offset_y = self.height()/2
        self.last_mouse_pos = None

        #caching the path to make faster
        self.num_buckets = 10
        self.min_speed = 0
        self.max_speed = 30

        self.paths = [QPainterPath() for _ in range(self.num_buckets)]
        self.bucket_colors = [
            QColor(
                int(255 * (i / (self.num_buckets - 1))),          # R
                int(255 * (1 - i / (self.num_buckets - 1))),      # G
                0                                                  # B
            )
            for i in range(self.num_buckets)
        ]

        #zoom settings
        self.zoom = 1.0
        self.zoom_min = 0.1
        self.zoom_max = 50.0

        #display setting
        self.scale = 10  # pixels per meter

        self.data: list[DataPoint] = list()

        #coloring the line
        self.speeds = []
        self.colors = []

        #grid state
        self.grid_cache = None

        #settings for playback
        self.points = []
        self.playback_index = 0
        self.ms_per_point = 100
        #only show one update in 50 becuase the GPS updates slower than the adafruit polls
        #this should not lose any data and be much easier to work with
        self.playback_step_size = 50

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.playback_step)
        self.update_grid_cache()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Draw background
        if self.grid_cache:
            p.drawPixmap(0, 0, self.grid_cache)

        #draw text in the top left corner
        p.setPen(QColor(255, 255, 255))
        p.setFont(p.font())

        if self.playback_index < len(self.data):
            t = self.data[self.playback_index].time/1000
            p.drawText(10, 20, f"Time: {t:.2f}s")
        elif(self.playback_index != 0):
            t = self.data[-1].time/1000
            p.drawText(10, 20, f"Time: {t:.2f}s")

        # Apply zoom around center
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(self.zoom, self.zoom)
        p.translate(-self.width() / 2, -self.height() / 2)

        offset = QPointF(self.offset_x, self.offset_y)

        # Draw path with speed-based color
        if len(self.points) > 1:
            # Draw cached paths by bucket
            for i, path in enumerate(self.paths):
                if not path.isEmpty():
                    p.setPen(QPen(self.bucket_colors[i], 3))
                    p.drawPath(path.translated(offset))

        # Draw current position dot
        if self.points:
            p.setPen(QPen(Qt.red, 6))
            p.drawPoint(self.points[-1] + offset)

    #for dragging veiw around with the mouse
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.pos()

    #update trigger to recach grid when display is resized
    def resizeEvent(self, event):
        self.update_grid_cache()
        super().resizeEvent(event)

    #zoom control
    def wheelEvent(self, event):
        zoom_factor = 1.15

        old_zoom = self.zoom

        if event.angleDelta().y() > 0:
            new_zoom = self.zoom * zoom_factor
        else:
            new_zoom = self.zoom / zoom_factor

        new_zoom = max(self.zoom_min, min(self.zoom_max, new_zoom))

        if new_zoom == old_zoom:
            return

        # mouse position in widget coordinates
        cursor = event.position()

        # adjust offset so cursor stays fixed
        self.offset_x = cursor.x() - (cursor.x() - self.offset_x) * (new_zoom / old_zoom)
        self.offset_y = cursor.y() - (cursor.y() - self.offset_y) * (new_zoom / old_zoom)

        #save zoom and update
        self.zoom = new_zoom
        self.update_grid_cache()
        self.update()

    def draw_grid(self, p):
        grid_spacing = 50  # pixels at zoom=1
        scaled_spacing = grid_spacing * self.zoom

        left = int((-self.offset_x) // scaled_spacing) - 1
        right = int((self.width() - self.offset_x) // scaled_spacing) + 1
        top = int((-self.offset_y) // scaled_spacing) - 1
        bottom = int((self.height() - self.offset_y) // scaled_spacing) + 1

        p.setPen(QPen(QColor(255, 255, 255, 30), 1))


        for x in range(left, right):
            px = x * scaled_spacing + self.offset_x
            p.drawLine(px, 0, px, self.height())

        for y in range(top, bottom):
            py = y * scaled_spacing + self.offset_y
            p.drawLine(0, py, self.width(), py)


    def mouseMoveEvent(self, event):
        if self.last_mouse_pos:
            dx = event.x() - self.last_mouse_pos.x()
            dy = event.y() - self.last_mouse_pos.y()

            self.offset_x += dx
            self.offset_y += dy

            self.last_mouse_pos = event.pos()
            self.update_grid_cache()
            self.update()

    def mouseReleaseEvent(self, event):
        self.last_mouse_pos = None

    def update_grid_cache(self):
        if self.width() <= 0 or self.height() <= 0:
            return
        self.grid_cache = QPixmap(self.size())
        self.grid_cache.fill(QColor("#350E0E"))
        p = QPainter(self.grid_cache)
        self.draw_grid(p)
        p.end()

    def speed_to_bucket(self, speed):
        speed = max(self.min_speed, min(self.max_speed, speed))
        t = (speed - self.min_speed) / (self.max_speed - self.min_speed)
        return int(t * (self.num_buckets - 1))

    def latlon_to_point(self, lat, lon):
        x = (lon) * 111_320
        y = -(lat) * 111_320

        return QPointF(x * self.scale, y * self.scale)

    def playback_step(self):
        if self.playback_index >= len(self.data):
            self.timer.stop()
            return

        latitude = self.data[self.playback_index].latitude
        longitude = self.data[self.playback_index].longitude
        acceleration = self.data[self.playback_index].acceleration
        speed = self.data[self.playback_index].speed

        point = self.latlon_to_point(latitude, longitude)
        
        self.main_window.text_console.log_message(
            f"playback status {point}"
        )

        if(speed > 0):
            self.output_speed.emit(speed)
        bucket = self.speed_to_bucket(speed)

        # add segment to correct bucket path
        if self.points:
            self.paths[bucket].moveTo(self.points[-1])
            self.paths[bucket].lineTo(point)
        else:
            self.paths[bucket].moveTo(point)

        self.points.append(point)
        self.playback_index += self.playback_step_size
        self.update()

    def set_playback_status(self, status):
        self.main_window.text_console.log_message(
            f"playback status {status}"
        )
        self.playback = status

        if status:
            #add this code back to change is so prev loaded points are cleard when pause it pressed
            #self.playback_index = 0
            #self.points.clear()
            self.timer.start(self.ms_per_point)  # ms per point
        else:
            self.timer.stop()

    def load_from_file(self, path):
        if(path == None):
            self.main_window.text_console.log_message(
            f"failed to load any points please provide a valid path"
            )
            return

        #clear any prev loaded points
        self.playback_index = 0
        self.points.clear()

        self.data.clear()

        with open(path, "r", newline="") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)

            # normalize header names
            header_map = {h.strip().lower(): i for i, h in enumerate(headers)}

            # possible column names
            try:
                lat_key = next(k for k in header_map if "lat" in k)
                lon_key = next(k for k in header_map if "lon" in k)
                time_key = next(k for k in header_map if "millis" in k)
                vx_imu_key = next(k for k in header_map if "vx_imu" in k)
                vy_imu_key = next(k for k in header_map if "vy_imu" in k)
                ax_w_key = next(k for k in header_map if "ax_w" in k)
                ay_w_key = next(k for k in header_map if "ay_w" in k)
            except StopIteration:
                self.main_window.text_console.log_message(
                    f"Loaded File does not have propper data labeling \n unable to load lon/lat data cols"
                )
                return

            lat_idx = header_map[lat_key]
            lon_idx = header_map[lon_key]
            time_idx = header_map[time_key]
            vx_imu_idx = header_map[vx_imu_key]
            vy_imu_idx = header_map[vy_imu_key]
            ax_w_idx = header_map[ax_w_key]
            ay_w_idx = header_map[ay_w_key]
            
            data_import_list: list[DataPoint] = list()

            for row in reader:
                try:
                    data_import_list.append(DataPoint(
                        x = float(row[lat_idx]), 
                        y = float(row[lon_idx]),
                        s = math.sqrt(float(row[vx_imu_idx])*float(row[vx_imu_idx])+float(row[vy_imu_idx])*float(row[vy_imu_idx])),
                        a = math.sqrt(float(row[ax_w_idx])*float(row[ax_w_idx])+float(row[ay_w_idx])*float(row[ay_w_idx])),
                        t = int(row[time_idx])
                        ))
                except (ValueError, IndexError):
                    continue  # skip bad rows

            #remove values from before the GPS inits
            self.rows_skiped = 0

            for d in data_import_list:
                if d.latitude != 0 and d.longitude != 0:
                    self.data.append(d)
                else: self.rows_skiped += 1

            self.main_window.text_console.log_message(
                f"Loaded {len(self.data)} Data Points. Skipped {self.rows_skiped} rows."
            )