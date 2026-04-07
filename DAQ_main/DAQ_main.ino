// =======================
// ====== INCLUDES =======
// =======================
#include <Wire.h>                 // I2C communication (BNO055)
#include <SPI.h>                  // SPI for SD card
#include <SD.h>                   // SD card logging
#include <HardwareSerial.h>       // UART2 for GPS
#include <TinyGPS.h>              // GPS parsing
#include <Adafruit_BNO055.h>      // IMU sensor
#include <Adafruit_Sensor.h>      // Sensor base class
#include <NimBLEDevice.h>         // <<< switched to NimBLE on ESP32
#include <math.h>                 // For trig and sqrt

// =======================
// ====== CONSTANTS ======
// =======================
SPIClass spi(FSPI);

// ----- Custom SPI pins for SD card -----
#define SD_SCK   39
#define SD_MOSI  42
#define SD_MISO  21
#define SD_CS    45

// ----- BLE UUIDs -----
#define SERVICE_UUID        "26efde6e-344c-47a4-bf50-78d548220c87"
#define REQUEST_UUID        "d69584e5-5142-414f-a90e-07c271d18574"
#define RESPONSE_UUID       "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1b"
#define TIMER_UUID          "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1c"
#define GPS_UUID            "d69584e5-5142-414f-a90e-07c271d18575"
#define IMU_UUID            "d69584e5-5142-414f-a90e-07c271d18576"

// address of the IMU on I2C
#define IMU_ADDR 0x6A

// ----- Physical constants -----
const double DEG_2_RAD = 0.01745329251;
const double EARTH_R   = 6371000.0;     // meters
const uint16_t BNO055_SAMPLERATE_DELAY_MS = 10;

// ============================
// ====== GLOBAL OBJECTS ======
// ============================

// IMU and GPS
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
HardwareSerial MySerial(2);  // UART2 for GPS (RX/TX pins defined later)
TinyGPS gps;
uint8_t bno_i2c_addr = 0x28;
bool imu_available = false;

// ---------- NimBLE objects (replaces ArduinoBLE) ----------
NimBLEServer*         bleServer   = nullptr;
NimBLEService*        daqService  = nullptr;
NimBLECharacteristic* requestChar = nullptr;
NimBLECharacteristic* responseChar= nullptr;
NimBLECharacteristic* timerChar   = nullptr;
NimBLECharacteristic* gpsChar     = nullptr;
NimBLECharacteristic* imuChar     = nullptr;

// SD file
File logfile;

// =============================
// ====== STATE VARIABLES ======
// =============================

// Raw integration states
double xPos = 0.0, yPos = 0.0;   // IMU-only position (world)
double vx = 0.0, vy = 0.0;       // IMU-only velocity
double ax_w = 0.0, ay_w = 0.0;   // accel in world frame
double latest_yaw_deg = 0.0;
double latest_roll_deg = 0.0;
double latest_pitch_deg = 0.0;
double latest_ax_b = 0.0;
double latest_ay_b = 0.0;
double latest_az_b = 0.0;

// Fused estimate (IMU + GPS)
double px_fused = 0.0, py_fused = 0.0;
double vx_fused = 0.0, vy_fused = 0.0;

// GPS reference origin
bool gps_origin_set = false;
double lat0 = 0.0, lon0 = 0.0, cos_lat0 = 1.0;
double xgps = 0.0, ygps = 0.0;
double last_xgps = 0.0, last_ygps = 0.0;
double vx_gps = 0.0, vy_gps = 0.0;

// Timing
uint32_t last_ms = 0;
uint32_t last_flush = 0;
uint32_t last_imu_debug_ms = 0;

// Fusion tuning (complementary filter)
const double ALPHA_V = 0.2;   // GPS velocity weight
const double BETA_P  = 0.02;  // GPS position weight

// Simple drift controls for IMU integration
const double IMU_ACCEL_DEADBAND = 0.05;   // m/s^2
const double IMU_VELOCITY_FLOOR = 0.02;   // m/s

// ============================
// ====== OTHER GLOBALS =======
// ============================

int pot_1 = 0;
int pot_2 = 0;
String line, line2; // temporary string buffers for CSV output

void writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(IMU_ADDR);
  Wire.write(reg);
  Wire.write(value);
  Wire.endTransmission();
}

int16_t read16(uint8_t reg) {
  Wire.beginTransmission(IMU_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(IMU_ADDR, 2);

  int16_t value = Wire.read();
  value |= (Wire.read() << 8);
  return value;
}

void setup() {
  // logging data on the 9600 band
  Serial.begin(9600);
  // We are using a 9600 baud GPS DO NOT CHANGE THE MAGIC NUMBER
  MySerial.begin(9600, SERIAL_8N1, 18, 1);  // (pins unchanged)

  spi.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);

  if (!SD.begin(SD_CS, spi, 4000000)) {
      Serial.println("SD card initialization failed!");
      while (1);
  }

  delay(2000);//give serial time to init

  //TODO IMU CHECKER GOES HERE

  if (!SD.begin(SD_CS, spi, 4000000)) {
    Serial.println("SD card initialization failed!");
    while (1);
  }
  Serial.println("SD card initialized.");

  logfile = SD.open("/datalog.csv", FILE_APPEND);
  if (!logfile) {
    Serial.println("Could not open datalog.csv");
    while (1);
  }

  // I2C speed & BNO external crystal (improves fusion quality)
  Wire.setClock(400000);

  bool bno_ok = bno.begin();
  if (!bno_ok) {
    bno = Adafruit_BNO055(55, 0x29);
    bno_ok = bno.begin();
    if (bno_ok) {
      bno_i2c_addr = 0x29;
    }
  }

  imu_available = bno_ok;
  if (imu_available) {
    Serial.print("BNO055 initialized on I2C address 0x");
    Serial.println(bno_i2c_addr, HEX);
    delay(100);
    bno.setExtCrystalUse(true);
  } else {
    Serial.println("BNO055 init failed on 0x28 and 0x29. Continuing without IMU so BLE remains available.");
  }

  // Add a header if this is a new file
  if (logfile && logfile.size() == 0) {
    logfile.println(
      "yaw_deg,roll_deg,pitch_deg,"
      "ax_b,ay_b,az_b,"
      "ax_w,ay_w,"
      "vx_imu,vy_imu,x_imu,y_imu,"          // IMU-propagated
      "lat,lon,xgps,ygps,vx_gps,vy_gps,"    // GPS-derived
      "x_fused,y_fused,vx_fused,vy_fused,"  // fused estimate
      "sys_cal,g_cal,a_cal,m_cal,"
      "millis"
    );
  }

  // --------- NimBLE init (replaces ArduinoBLE.begin etc.) ----------
  NimBLEDevice::init("CAR_GO_VROOM");
  // Optional tweaks:
  NimBLEDevice::setSecurityAuth(false, false, false); // no pairing
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);             // max TX power
  // NimBLEDevice::setMTU(247); // optional larger MTU if streaming data

  bleServer  = NimBLEDevice::createServer();

  daqService = bleServer->createService(SERVICE_UUID);

  requestChar = daqService->createCharacteristic(
    REQUEST_UUID,
    NIMBLE_PROPERTY::WRITE
  );
  responseChar = daqService->createCharacteristic(
    RESPONSE_UUID,
    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY
  );
  timerChar = daqService->createCharacteristic(
    TIMER_UUID,
    NIMBLE_PROPERTY::READ
  );
  gpsChar = daqService->createCharacteristic(
    GPS_UUID,
    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE
  );
  imuChar = daqService->createCharacteristic(
    IMU_UUID,
    NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE
  );

  // initial GPS-fix flag = 0 and clear imu data
  uint8_t zero = 0;
  gpsChar->setValue(&zero, 1);
  imuChar->setValue(&zero, 1);

  daqService->start();

  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();

  NimBLEAdvertisementData advData;
  advData.setName("CAR_GO_VROOM");
  advData.setFlags(0x06); // LE General Discoverable + BR/EDR Not Supported
  advData.addServiceUUID(daqService->getUUID());
  adv->setAdvertisementData(advData);

  // Optional scan response with name too (some scanners prefer it here)
  NimBLEAdvertisementData scanResp;
  scanResp.setName("CAR_GO_VROOM");
  adv->setScanResponseData(scanResp);

  adv->start();

  Serial.println("NimBLE Peripheral - Advertising");
}


void loop() {
  // NOTE: NimBLE does not need BLE.poll()

  static uint32_t next_sample = 0;
  uint32_t now = millis();
  if (now < next_sample) return;
  next_sample = now + BNO055_SAMPLERATE_DELAY_MS;

  double dt = (last_ms == 0) ? (BNO055_SAMPLERATE_DELAY_MS / 1000.0)
                             : (now - last_ms) / 1000.0;
  last_ms = now;

  // GPS byte pump
  while (MySerial.available()) {
    gps.encode(MySerial.read());
  }

  // Update IMU and GPS, then fuse, then log
  updateIMU(dt);
  updateGPS(dt);
  fuseEstimates(dt);
  send_BLE_data();
  //write CSV 
  writeCSV(now);
}

void send_BLE_data(){
  // get lat-lon
  float flat, flon; unsigned long age;
  gps.f_get_position(&flat, &flon, &age);
  if (flat == TinyGPS::GPS_INVALID_F_ANGLE) flat = 0.0;
  if (flon == TinyGPS::GPS_INVALID_F_ANGLE) flon = 0.0;
  // ---- BLE GPS fix flag via NimBLE ----
  float gpsOut[2] = {flat, flon};
  
  if (gpsChar) {
    gpsChar->setValue(gpsOut);
    // Notify if you want push updates to the phone/app:
    gpsChar->notify();
  }

  // Keep BLE payload shape stable for GUI parser:
  // yaw, roll, pitch, ax_b, ay_b, az_b, ax_w, ay_w, vx, vy, x, y
  float imuOut[12] = {
    (float)latest_yaw_deg,
    (float)latest_roll_deg,
    (float)latest_pitch_deg,
    (float)latest_ax_b,
    (float)latest_ay_b,
    (float)latest_az_b,
    (float)ax_w,
    (float)ay_w,
    (float)vx,
    (float)vy,
    (float)xPos,
    (float)yPos
  };

  if (imuChar) {
    imuChar->setValue((uint8_t*)imuOut, sizeof(imuOut));
    imuChar->notify();
  }
}

void writeCSV(uint32_t now_ms) {
  // Calibration levels
  uint8_t sys=0, g=0, a=0, m=0;
  if (imu_available) {
    bno.getCalibration(&sys, &g, &a, &m);
  }

  // Build line (you can keep String for now; swap to snprintf later if needed)
  String s;
  s.reserve(200);

  s += String(latest_yaw_deg, 6); s += ",";           // yaw
  s += String(latest_roll_deg, 6); s += ",";          // roll
  s += String(latest_pitch_deg, 6); s += ",";         // pitch

  s += String(latest_ax_b, 6); s += ",";              // ax_b
  s += String(latest_ay_b, 6); s += ",";              // ay_b
  s += String(latest_az_b, 6); s += ",";              // az_b

  s += String(ax_w, 6); s += ",";                     // ax_w
  s += String(ay_w, 6); s += ",";                     // ay_w

  s += String(vx, 6); s += ",";                       // vx_imu
  s += String(vy, 6); s += ",";                       // vy_imu
  s += String(xPos, 6); s += ",";                     // x_imu
  s += String(yPos, 6); s += ",";                     // y_imu

  // GPS lat/lon + local meters + GPS vel
  float flat, flon; unsigned long age;
  gps.f_get_position(&flat, &flon, &age);
  if (flat == TinyGPS::GPS_INVALID_F_ANGLE) flat = 0.0;
  if (flon == TinyGPS::GPS_INVALID_F_ANGLE) flon = 0.0;

  s += String(flat, 6); s += ",";
  s += String(flon, 6); s += ",";
  s += String(xgps, 6); s += ",";
  s += String(ygps, 6); s += ",";
  s += String(vx_gps, 6); s += ",";
  s += String(vy_gps, 6); s += ",";

  // Fused
  s += String(px_fused, 6); s += ",";
  s += String(py_fused, 6); s += ",";
  s += String(vx_fused, 6); s += ",";
  s += String(vy_fused, 6); s += ",";

  // Cal + time
  s += String(sys); s += ","; s += String(g); s += ","; s += String(a); s += ","; s += String(m); s += ",";
  s += String(now_ms);

  Serial.println(s);
  logfile.println(s);

  if (now_ms - last_flush > 1000) { logfile.flush(); last_flush = now_ms; }
}

void updateIMU(double dt) {
  if (!imu_available) {
    latest_yaw_deg = 0.0;
    latest_roll_deg = 0.0;
    latest_pitch_deg = 0.0;
    latest_ax_b = 0.0;
    latest_ay_b = 0.0;
    latest_az_b = 0.0;
    ax_w = 0.0;
    ay_w = 0.0;
    vx = 0.0;
    vy = 0.0;
    return;
  }

  sensors_event_t euler, lin;
  bno.getEvent(&euler, Adafruit_BNO055::VECTOR_EULER);         // x=head(yaw), y=roll, z=pitch (deg)
  bno.getEvent(&lin,   Adafruit_BNO055::VECTOR_LINEARACCEL);   // body-frame, gravity removed (m/s^2)

  latest_yaw_deg = euler.orientation.x;
  latest_roll_deg = euler.orientation.y;
  latest_pitch_deg = euler.orientation.z;

  latest_ax_b = lin.acceleration.x;
  latest_ay_b = lin.acceleration.y;
  latest_az_b = lin.acceleration.z;

  double yaw = latest_yaw_deg * DEG_2_RAD;

  // Body -> world (flat car): rotate by yaw around Z
  double ax_b = latest_ax_b;
  double ay_b = latest_ay_b;

  ax_w =  ax_b * cos(yaw) - ay_b * sin(yaw);
  ay_w =  ax_b * sin(yaw) + ay_b * cos(yaw);

  // Deadband removes tiny bias/noise that otherwise integrates forever.
  if (fabs(ax_w) < IMU_ACCEL_DEADBAND) ax_w = 0.0;
  if (fabs(ay_w) < IMU_ACCEL_DEADBAND) ay_w = 0.0;

  vx += ax_w * dt;
  vy += ay_w * dt;

  if (fabs(vx) < IMU_VELOCITY_FLOOR && fabs(ax_w) == 0.0) vx = 0.0;
  if (fabs(vy) < IMU_VELOCITY_FLOOR && fabs(ay_w) == 0.0) vy = 0.0;

  xPos += vx * dt + 0.5 * ax_w * dt * dt;
  yPos += vy * dt + 0.5 * ay_w * dt * dt;

  uint32_t now_ms = millis();
  if (now_ms - last_imu_debug_ms >= 1000) {
    last_imu_debug_ms = now_ms;
    Serial.print("IMU dbg yaw="); Serial.print(latest_yaw_deg, 3);
    Serial.print(" roll="); Serial.print(latest_roll_deg, 3);
    Serial.print(" pitch="); Serial.print(latest_pitch_deg, 3);
    Serial.print(" ax_b="); Serial.print(latest_ax_b, 3);
    Serial.print(" ay_b="); Serial.print(latest_ay_b, 3);
    Serial.print(" az_b="); Serial.print(latest_az_b, 3);
    Serial.print(" ax_w="); Serial.print(ax_w, 3);
    Serial.print(" ay_w="); Serial.print(ay_w, 3);
    Serial.print(" vx="); Serial.print(vx, 3);
    Serial.print(" vy="); Serial.println(vy, 3);
  }
}

bool gpsHasFreshFix(uint32_t &age_ms) {
  float flat, flon;
  unsigned long age;
  gps.f_get_position(&flat, &flon, &age);
  age_ms = (age == TinyGPS::GPS_INVALID_AGE) ? 1000000UL : (uint32_t)age;
  return !(flat == TinyGPS::GPS_INVALID_F_ANGLE || flon == TinyGPS::GPS_INVALID_F_ANGLE);
}

void updateGPS(double dt) {
  uint32_t age_ms = 1000000;
  float flat, flon;
  unsigned long age;
  gps.f_get_position(&flat, &flon, &age);

  bool valid = !(flat == TinyGPS::GPS_INVALID_F_ANGLE || flon == TinyGPS::GPS_INVALID_F_ANGLE);
  if (!valid) return;

  if (!gps_origin_set) {
    lat0 = flat * DEG_2_RAD;
    lon0 = flon * DEG_2_RAD;
    cos_lat0 = cos(lat0);
    gps_origin_set = true;
    last_xgps = xgps = 0.0;
    last_ygps = ygps = 0.0;
    vx_gps = vy_gps = 0.0;
    return;
  }

  // Convert to local ENU meters (approx)
  double lat = flat * DEG_2_RAD;
  double lon = flon * DEG_2_RAD;
  xgps = EARTH_R * cos_lat0 * (lon - lon0);
  ygps = EARTH_R * (lat - lat0);

  if (dt > 0.0001) {
    double raw_vx = (xgps - last_xgps) / dt;
    double raw_vy = (ygps - last_ygps) / dt;

    // Optional: mild low-pass on GPS velocity to reduce jitter
    const double GPS_VEL_LP = 0.3;
    vx_gps = (1.0 - GPS_VEL_LP) * vx_gps + GPS_VEL_LP * raw_vx;
    vy_gps = (1.0 - GPS_VEL_LP) * vy_gps + GPS_VEL_LP * raw_vy;
  }

  last_xgps = xgps;
  last_ygps = ygps;
}

void fuseEstimates(double dt) {
  bool have_gps = gps_origin_set; // could also check recent age if you store it

  if (have_gps) {
    // Fuse velocities first (IMU propagate + GPS correction)
    double vx_pred = vx_fused + ax_w * dt;
    double vy_pred = vy_fused + ay_w * dt;
    vx_fused = (1.0 - ALPHA_V) * vx_pred + ALPHA_V * vx_gps;
    vy_fused = (1.0 - ALPHA_V) * vy_pred + ALPHA_V * vy_gps;

    // Fuse positions (propagate with fused v, correct toward GPS position)
    double px_pred = px_fused + vx_fused * dt;
    double py_pred = py_fused + vy_fused * dt;
    px_fused = (1.0 - BETA_P) * px_pred + BETA_P * xgps;
    py_fused = (1.0 - BETA_P) * py_pred + BETA_P * ygps;

    // Optional ZUPT:
    // if (hypot(vx_gps,vy_gps) < 0.3 && fabs(ax_w) < 0.1 && fabs(ay_w) < 0.1) { vx_fused = vy_fused = 0; }
  } else {
    // No GPS → pure IMU propagate
    vx_fused += ax_w * dt;
    vy_fused += ay_w * dt;
    px_fused += vx_fused * dt;
    py_fused += vy_fused * dt;
  }
}