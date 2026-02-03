from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QPainterPath
from PySide6.QtCore import Qt, QPointF, QTimer, Signal
import csv
import math

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

        #imu data
        self.vxs_imu = []
        self.vys_imu = []

        # GPS data
        self.lats = []
        self.lons = []
        self.times = []
        self.lat_offset = 0.0
        self.lon_offset = 0.0
        self.time_offset = 0.0

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

        if self.playback_index < len(self.times):
            t = self.times[self.playback_index]/1000
            p.drawText(10, 20, f"Time: {t:.2f}s")
        elif(self.playback_index != 0):
            t = self.times[-1]/1000
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
         # Earth radius approximation
        meters_per_deg_lat = 111_320
        meters_per_deg_lon = 111_320 * math.cos(math.radians(self.lat_offset))

        x = (lon - self.lon_offset) * meters_per_deg_lon
        y = -(lat - self.lat_offset) * meters_per_deg_lat

        return QPointF(x * self.scale, y * self.scale)

    def playback_step(self):
        if self.playback_index >= len(self.lats):
            self.timer.stop()
            return

        lat = self.lats[self.playback_index]
        lon = self.lons[self.playback_index]
        vx_imu = self.vxs_imu[self.playback_index]
        vy_imu = self.vys_imu[self.playback_index]
        
        velocity_imu = math.sqrt(vx_imu**2 + vy_imu**2) * 2.23693629 #convertion factior from meters/s to miles/h

        point = self.latlon_to_point(lat, lon)

        # compute speed
        if self.points:
            try:
                prev_point = self.points[self.playback_index - self.playback_step_size]
            except IndexError:
                prev_point = self.points[-1]
            dx = point.x() - prev_point.x()
            dy = point.y() - prev_point.y()
            distance = math.sqrt(dx * dx + dy * dy) #gives distance in m * display scale factor
            deltaTime = self.times[self.playback_index] - self.times[self.playback_index - self.playback_step_size]
            if(deltaTime <= 0):
                print("delta time <0")
                return
            speed = (distance/self.scale) / (deltaTime/1000) #speed in meters/s
            speed *= 2.23693629 #convertion factior from meters/s to miles/h
            speed = velocity_imu
        else:
            speed = 0

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

        self.lats.clear()
        self.lons.clear()
        self.vxs_imu.clear()
        self.vys_imu.clear()

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

            for row in reader:
                try:
                    self.lats.append(float(row[lat_idx]))
                    self.lons.append(float(row[lon_idx]))
                    self.times.append(int(row[time_idx]))
                    self.vxs_imu.append(float(row[vx_imu_idx]))
                    self.vys_imu.append(float(row[vy_imu_idx]))
                except (ValueError, IndexError):
                    continue  # skip bad rows

        #remove values from before the GPS inits
        new_lats = []
        new_lons = []
        new_vxs_imu = []
        new_vys_imu = []
        new_times = []
        self.rows_skiped = 0

        for lat, lon, vx_imu, vy_imu, time in zip(self.lats, self.lons, self.vxs_imu, self.vys_imu, self.times):
            if lat != 0 and lon != 0:
                new_lats.append(lat)
                new_lons.append(lon)
                new_vxs_imu.append(vx_imu)
                new_vys_imu.append(vy_imu)
                new_times.append(time)
                self.rows_skiped += 1

        self.lats = new_lats
        self.lons = new_lons
        self.vxs_imu = new_vxs_imu
        self.vys_imu = new_vys_imu
        self.times = new_times

        self.lat_offset = self.lats[0]
        self.lon_offset = self.lons[0]
        self.vx_imu = self.vxs_imu[0]
        self.vy_imu = self.vys_imu[0]
        self.time_offset = self.times[0]

        self.main_window.text_console.log_message(
            f"Loaded {len(self.lats)} GPS points (lat, lon)\n Loaded {len(self.vxs_imu)} IMU velocity points (vx_imu, vy_imu)\n skipped {self.rows_skiped} rows with no GPS lock"
        )