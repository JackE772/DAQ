from PySide6.QtWidgets import QWidget, QInputDialog
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QPainterPath
from PySide6.QtCore import Qt, QPointF, QTimer, Signal
import csv
import math
import os
import time

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
    output_acceleration = Signal(float) #tuple of (ax, ay, az) in m/s^2
    display_mode_changed = Signal(str)
    playback_position_changed = Signal(int, int, int)
    playback_range_changed = Signal(int, int)

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
                int(255 * (1 - i / (self.num_buckets - 1))),       # R
                0,                                                 # G
                0                                                  # B
            )
            for i in range(self.num_buckets)
        ]

        #zoom settings
        self.zoom = 1.0
        self.zoom_min = 0.1
        self.zoom_max = 50.0
        self.zoom_scroll_remainder = 0.0

        #display setting
        self.scale = 10  # pixels per meter

        self.data: list[DataPoint] = list()
        self.lat_offset = 0
        self.lon_offset = 0

        #coloring the line
        self.speeds = []
        self.colors = []

        #grid state
        self.grid_cache = None

        #settings for playback
        self.points = []
        self.playback_index = 0
        self.current_index = 0
        self.current_file_mode = "legacy"
        self.ms_per_point = 100
        self.live_start_time_s = None
        #only show one update in 50 becuase the GPS updates slower than the adafruit polls
        #this should not lose any data and be much easier to work with
        self.playback_step_size = 50

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.playback_step)
        self.update_grid_cache()
        self.update()

    def configure_for_live_mode(self):
        self.playback_step_size = 1
        self.ms_per_point = 50
        self.display_mode_changed.emit("map")
        if self.playback_index >= len(self.data):
            self.playback_index = max(0, len(self.data) - 1)

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
        scroll_delta = event.angleDelta().y()
        if scroll_delta == 0:
            scroll_delta = event.pixelDelta().y()

        if scroll_delta == 0:
            return

        self.zoom_scroll_remainder += scroll_delta
        threshold = 90.0
        if abs(self.zoom_scroll_remainder) < threshold:
            return

        steps = int(abs(self.zoom_scroll_remainder) // threshold)
        direction = 1 if self.zoom_scroll_remainder > 0 else -1
        self.zoom_scroll_remainder -= direction * steps * threshold

        zoom_factor = 1.08 ** steps

        old_zoom = self.zoom
        if direction > 0:
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

    def get_time(self):
        if self.current_index < len(self.data):
            return self.data[self.current_index].time
        else:
            return 0

    def get_data_length(self):
        return len(self.data)

    def get_current_index(self):
        if not self.data:
            return 0
        return max(0, min(self.current_index, len(self.data) - 1))

    def get_total_time_ms(self):
        if not self.data:
            return 0
        return int(self.data[-1].time)

    def _emit_vcu_payload(self, data_point):
        if not hasattr(self.main_window, "vcu_telemetry_updated"):
            return

        if hasattr(data_point, "battery_percent"):
            self.main_window.vcu_telemetry_updated.emit({
                "is_vcu": True,
                "line_number": getattr(data_point, "line_number", None),
                "time_ms": getattr(data_point, "time_ms", data_point.time),
                "speed_mph": getattr(data_point, "speed_mph", None),
                "speed_mps": data_point.speed,
                "battery_percent": getattr(data_point, "battery_percent", 0.0),
                "dc_current": getattr(data_point, "dc_current", None),
                "ac_current": getattr(data_point, "ac_current", None),
                "ac_voltage": getattr(data_point, "ac_voltage", None),
            })
        else:
            self.main_window.vcu_telemetry_updated.emit({"is_vcu": False})

    def _emit_outputs_for_index(self, index):
        if not self.data:
            return

        data_point = self.data[index]
        self.output_speed.emit(data_point.speed)
        self.output_acceleration.emit(data_point.acceleration)
        self._emit_vcu_payload(data_point)

    def _emit_playback_position(self, index):
        if not self.data:
            self.playback_position_changed.emit(0, 0, 0)
            return

        current_time = int(self.data[index].time)
        total_time = int(self.data[-1].time)
        self.playback_position_changed.emit(index, current_time, total_time)

    def _rebuild_path_to_index(self, end_index):
        self.points.clear()
        self.paths = [QPainterPath() for _ in range(self.num_buckets)]

        if not self.data or end_index < 0:
            return

        previous_point = None
        last_index = min(end_index, len(self.data) - 1)
        for index in range(last_index + 1):
            data_point = self.data[index]
            point = self.latlon_to_point(data_point.latitude, data_point.longitude)
            bucket = self.speed_to_bucket(data_point.speed)

            if previous_point is None:
                self.paths[bucket].moveTo(point)
            else:
                self.paths[bucket].moveTo(previous_point)
                self.paths[bucket].lineTo(point)

            self.points.append(point)
            previous_point = point

    def seek_to_index(self, index):
        if not self.data:
            return

        clamped_index = max(0, min(index, len(self.data) - 1))
        self.playback_index = clamped_index
        self.current_index = clamped_index

        self._rebuild_path_to_index(clamped_index)
        self._emit_outputs_for_index(clamped_index)
        self._emit_playback_position(clamped_index)
        self.update()

    def clear_loaded_state(self):
        self.timer.stop()
        self.playback = False
        self.zoom_scroll_remainder = 0.0

        self.data.clear()
        self.points.clear()
        self.paths = [QPainterPath() for _ in range(self.num_buckets)]

        self.playback_index = 0
        self.current_index = 0
        self.rows_skiped = 0
        self.lat_offset = 0
        self.lon_offset = 0
        self.live_start_time_s = None

        self.playback_range_changed.emit(0, 0)
        self.playback_position_changed.emit(0, 0, 0)
        if hasattr(self.main_window, "vcu_telemetry_updated"):
            self.main_window.vcu_telemetry_updated.emit({"is_vcu": False})

        self.update()

    def latlon_to_point(self, lat, lon):
        # Earth radius approximation
        meters_per_deg_lat = 111_320
        meters_per_deg_lon = 111_320 * math.cos(math.radians(self.lat_offset))

        x = (lon - self.lon_offset) * meters_per_deg_lon
        y = -(lat - self.lat_offset) * meters_per_deg_lat
        return QPointF(x * self.scale, y * self.scale)

    def playback_step(self):
        if self.playback_index >= len(self.data):
            self.timer.stop()
            return

        current_index = self.playback_index
        self.current_index = current_index
        current_data = self.data[current_index]
        latitude = current_data.latitude
        longitude = current_data.longitude
        acceleration = current_data.acceleration
        speed = current_data.speed

        point = self.latlon_to_point(latitude, longitude)

        self._emit_outputs_for_index(current_index)

        bucket = self.speed_to_bucket(speed)

        # add segment to correct bucket path
        if self.points:
            self.paths[bucket].moveTo(self.points[-1])
            self.paths[bucket].lineTo(point)
        else:
            self.paths[bucket].moveTo(point)

        self.points.append(point)
        self._emit_playback_position(current_index)
        self.playback_index += self.playback_step_size
        self.update()

    def set_playback_status(self, status):
        self.playback = status

        if getattr(self.main_window, "sourceType", None) == "Bluetooth" and not getattr(self.main_window, "bluetooth_review_mode", False):
            self.timer.stop()
            return

        if status:
            #add this code back to change is so prev loaded points are cleard when pause it pressed
            #self.playback_index = 0
            #self.points.clear()
            self.timer.start(self.ms_per_point)  # ms per point
        else:
            self.timer.stop()

    def _resolve_file_mode(self, path):
        filename = os.path.basename(path).lower()

        if filename.startswith("vcu_"):
            return "vcu"
        if filename.startswith("gps_") or filename.startswith("imu_"):
            return "legacy"

        choice, accepted = QInputDialog.getItem(
            self,
            "Select File Format",
            (
                "Could not detect file format from filename prefix.\n"
                "Use 'vcu_' for new VCU logs or 'gps_'/'imu_' for legacy logs.\n"
                "Choose format for this file:"
            ),
            ["Legacy (gps_/imu_)", "VCU (vcu_)"]
        )

        if not accepted:
            return None
        return "vcu" if "VCU" in choice else "legacy"

    def _load_legacy_file(self, rows):
        if not rows:
            raise ValueError("Loaded file is empty")

        headers = rows[0]
        data_rows = rows[1:]

        # normalize header names
        header_map = {h.strip().lower(): i for i, h in enumerate(headers)}

        try:
            lat_key = next(k for k in header_map if "lat" in k)
            lon_key = next(k for k in header_map if "lon" in k)
            time_key = next(k for k in header_map if "millis" in k)
            vx_imu_key = next(k for k in header_map if "vx_imu" in k)
            vy_imu_key = next(k for k in header_map if "vy_imu" in k)
            ax_w_key = next(k for k in header_map if "ax_w" in k)
            ay_w_key = next(k for k in header_map if "ay_w" in k)
        except StopIteration as exc:
            raise ValueError(
                "Loaded file does not have proper legacy labels for lon/lat/time/IMU columns"
            ) from exc

        lat_idx = header_map[lat_key]
        lon_idx = header_map[lon_key]
        time_idx = header_map[time_key]
        vx_imu_idx = header_map[vx_imu_key]
        vy_imu_idx = header_map[vy_imu_key]
        ax_w_idx = header_map[ax_w_key]
        ay_w_idx = header_map[ay_w_key]

        data_import_list: list[DataPoint] = []
        for row in data_rows:
            try:
                data_import_list.append(DataPoint(
                    x=float(row[lat_idx]),
                    y=float(row[lon_idx]),
                    s=math.sqrt(float(row[vx_imu_idx]) * float(row[vx_imu_idx]) + float(row[vy_imu_idx]) * float(row[vy_imu_idx])),
                    a=math.sqrt(float(row[ax_w_idx]) * float(row[ax_w_idx]) + float(row[ay_w_idx]) * float(row[ay_w_idx])),
                    t=int(float(row[time_idx]))
                ))
            except (ValueError, IndexError):
                continue

        skipped_rows = 0
        output_data: list[DataPoint] = []
        for data_point in data_import_list:
            if data_point.latitude != 0 and data_point.longitude != 0:
                output_data.append(data_point)
            else:
                skipped_rows += 1

        return output_data, skipped_rows

    def _load_vcu_file(self, rows):
        if not rows:
            raise ValueError("Loaded file is empty")

        MPH_TO_MPS = 0.44704
        METERS_PER_DEGREE = 111_320.0

        start_idx = 0
        # Accept optional header row; data rows should be numeric and include at least 7 columns.
        if len(rows[0]) < 7:
            start_idx = 1
        else:
            try:
                float(rows[0][1])
                float(rows[0][2])
            except (ValueError, IndexError):
                start_idx = 1

        data_rows = rows[start_idx:]
        output_data: list[DataPoint] = []

        prev_time_ms = None
        prev_speed_mps = None
        distance_m = 0.0
        skipped_rows = 0

        for row in data_rows:
            try:
                if len(row) < 7:
                    raise ValueError("Not enough columns")

                time_ms = int(float(row[1]))
                line_number = int(float(row[0]))
                speed_mps = float(row[2]) * MPH_TO_MPS
                speed_mph = float(row[2])

                acceleration = 0.0
                if prev_time_ms is not None and prev_speed_mps is not None:
                    dt_s = (time_ms - prev_time_ms) / 1000.0
                    if dt_s > 0:
                        acceleration = abs((speed_mps - prev_speed_mps) / dt_s)
                        distance_m += speed_mps * dt_s

                latitude = distance_m / METERS_PER_DEGREE
                longitude = 0.0

                data_point = DataPoint(
                    x=latitude,
                    y=longitude,
                    s=speed_mps,
                    a=acceleration,
                    t=time_ms,
                )

                # Preserve VCU-specific telemetry for future UI usage.
                data_point.dc_current = float(row[3])
                data_point.ac_current = float(row[4])
                data_point.ac_voltage = float(row[5])
                data_point.battery_percent = max(0.0, min(100.0, float(row[6])))
                data_point.line_number = line_number
                data_point.time_ms = time_ms
                data_point.speed_mph = speed_mph

                output_data.append(data_point)
                prev_time_ms = time_ms
                prev_speed_mps = speed_mps
            except (ValueError, IndexError):
                skipped_rows += 1
                continue

        return output_data, skipped_rows

    def load_from_file(self, path):
        if(path == None):
            self.main_window.text_console.log_message(
            f"failed to load any points please provide a valid path"
            )
            return

        #clear any prev loaded points
        self.playback_index = 0
        self.current_index = 0
        self.points.clear()

        self.data.clear()
        self.paths = [QPainterPath() for _ in range(self.num_buckets)]

        mode = self._resolve_file_mode(path)
        if mode is None:
            self.main_window.text_console.log_message(
                "File format selection canceled. No data loaded.",
                level="WARN"
            )
            return

        if mode == "vcu":
            self.current_file_mode = "vcu"
            self.display_mode_changed.emit("vcu")
        else:
            self.current_file_mode = "legacy"
            self.display_mode_changed.emit("map")

        try:
            rows = self._read_rows_csv_first(path)

            if mode == "vcu":
                self.data, self.rows_skiped = self._load_vcu_file(rows)
            else:
                self.data, self.rows_skiped = self._load_legacy_file(rows)
        except (OSError, ValueError) as exc:
            self.main_window.text_console.log_message(str(exc), level="ERROR")
            return

        if not self.data:
            self.main_window.text_console.log_message(
                f"No valid rows found in file ({mode} mode).",
                level="ERROR"
            )
            return

        self.lat_offset = self.data[0].latitude
        self.lon_offset = self.data[0].longitude

        self.main_window.text_console.log_message(
            (
                f"Loaded {len(self.data)} Data Points in {mode.upper()} mode. "
                f"Skipped {self.rows_skiped} rows.\n"
                f"Max Speed: {max(self.data, key=lambda x: x.speed).speed:.2f} m/s\n"
                f"Max Acceleration: {max(self.data, key=lambda x: x.acceleration).acceleration:.2f} m/s²"
            ),
            level="SUCCESS"
        )

        self.playback_range_changed.emit(max(0, len(self.data) - 1), int(self.data[-1].time))
        self.seek_to_index(0)

    def _read_rows_csv_first(self, path):
        with open(path, "r", encoding="utf-8", newline="") as raw_file:
            raw_text = raw_file.read()

        if not raw_text.strip():
            raise ValueError("Loaded file is empty")

        # First pass: default CSV reader (comma-delimited).
        rows = list(csv.reader(raw_text.splitlines()))
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if rows and max(len(row) for row in rows) > 1:
            return rows

        # Second pass: infer delimiter for common delimited text formats.
        try:
            sample = "\n".join(raw_text.splitlines()[:15])
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            rows = list(csv.reader(raw_text.splitlines(), dialect))
            rows = [row for row in rows if any(cell.strip() for cell in row)]
            if rows and max(len(row) for row in rows) > 1:
                self.main_window.text_console.log_message(
                    "Parsed file using detected delimiter (not plain comma CSV).",
                    level="INFO"
                )
                return rows
        except csv.Error:
            pass

        # Final fallback: split whitespace-delimited logs into columns.
        whitespace_rows = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            whitespace_rows.append(stripped.split())

        if whitespace_rows and max(len(row) for row in whitespace_rows) > 1:
            self.main_window.text_console.log_message(
                "CSV parse failed; used whitespace-delimited fallback parser.",
                level="WARN"
            )
            return whitespace_rows

        return rows
            
    def load_data_point(self, point, emit_update=True):
        try:
            # Prefer GPS coordinates for map placement, fallback to IMU-propagated x/y.
            if "lat" in point and "lon" in point:
                x = float(point["lat"])
                y = float(point["lon"])
            else:
                x = float(point.get("x", 0.0))
                y = float(point.get("y", 0.0))

            if "speed" in point:
                speed = float(point["speed"])
            else:
                speed = math.sqrt(
                    float(point.get("vx", 0.0)) * float(point.get("vx", 0.0))
                    + float(point.get("vy", 0.0)) * float(point.get("vy", 0.0))
                )

            if "ax" in point or "ay" in point or "az" in point:
                acceleration = math.sqrt(
                    float(point.get("ax", 0.0)) * float(point.get("ax", 0.0))
                    + float(point.get("ay", 0.0)) * float(point.get("ay", 0.0))
                    + float(point.get("az", 0.0)) * float(point.get("az", 0.0))
                )
            elif "ax_w" in point and "ay_w" in point:
                acceleration = math.sqrt(
                    float(point["ax_w"]) * float(point["ax_w"])
                    + float(point["ay_w"]) * float(point["ay_w"])
                )
            else:
                acceleration = 0.0

            if self.live_start_time_s is None:
                self.live_start_time_s = time.monotonic()
            elapsed_ms = int((time.monotonic() - self.live_start_time_s) * 1000)

            if len(self.data) == 0:
                self.lat_offset = x
                self.lon_offset = y

            self.data.append(DataPoint(
                x=x,
                y=y,
                s=speed,
                a=acceleration,
                t=elapsed_ms
            ))

            if emit_update:
                # In live mode, emit immediately so telemetry widgets update even
                # between timer playback ticks.
                new_index = len(self.data) - 1
                self.current_index = new_index

                if getattr(self.main_window, "sourceType", None) == "Bluetooth" and not getattr(self.main_window, "bluetooth_review_mode", False):
                    self.playback_index = new_index
                elif self.playback_index >= len(self.data):
                    self.playback_index = new_index

                self._emit_outputs_for_index(new_index)
                self._emit_playback_position(new_index)
                self.update()
        except (KeyError, TypeError, ValueError):
            self.main_window.text_console.log_message("Skipped invalid live data point")