import math, csv
from PySide6.QtCore import Qt, QPointF, QTimer, Signal
from PySide6.QtWidgets import QWidget

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
          
class Player(QWidget):
    rows_skiped = 0
    playback = False
    output_data = Signal
    output_console = Signal

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        
        self.output_console = Signal(str)
        self.output_data = Signal(list[DataPoint])
        

        #listens to main window for updates
        main_window.gps_updated.connect(self.load_from_file)
        main_window.playback.connect(self.set_playback_status)

        self.data: list[DataPoint] = list()

        #coloring the line
        self.speeds = []
        self.colors = []

        #settings for playback
        self.points = []
        self.playback_index = 0
        self.ms_per_point = 100
        #only show one update in 50 becuase the GPS updates slower than the adafruit polls
        #this should not lose any data and be much easier to work with
        self.playback_step_size = 50

        self.timer = QTimer()
        self.timer.timeout.connect(self.playback_step)
        
    def get_time(self):
        if self.playback_index < len(self.data):
            return self.data[self.playback_index].time
        elif(self.playback_index != 0):
            return self.data[-1].time
        else:
            return 0

    def playback_step(self):
        if self.playback_index >= len(self.data):
            self.timer.stop()
            return

        if(self.data[self.playback_index].speed > 0):
            self.output_data.emit(self.data[self.playback_index])

        self.playback_index += self.playback_step_size

    def set_playback_status(self, status):
        self.output_console.emit(
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
            self.output_console.emit(
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
                self.output_console.emit(
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

            self.output_console.emit(
                f"Loaded {len(self.data)} Data Points. Skipped {self.rows_skiped} rows."
            )
            
    def get_output_signal(self):
        return self.output_data