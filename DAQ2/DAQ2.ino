// ============================================================
//  DAQ2  –  ESP32-S3 DevKitC-1
//  Reads BNO085 (I2C) + GPS (UART), streams CSV over USB Serial,
//  logs to SD card, and broadcasts over BLE (NimBLE).
//
//  Required libraries (install via Arduino Library Manager):
//    - Adafruit BNO08x          (search "Adafruit BNO08x")
//    - Adafruit Unified Sensor  (dependency of above)
//    - TinyGPSPlus              (search "TinyGPSPlus")
//    - NimBLE-Arduino           (search "NimBLE-Arduino")
//    - SD (built-in ESP32 core)
// ============================================================

#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_BNO08x.h>
#include <TinyGPSPlus.h>
#include <NimBLEDevice.h>

// ── Pin Definitions ──────────────────────────────────────────
#define I2C_SDA     8
#define I2C_SCL     9

#define GPS_RX_PIN  18
#define GPS_TX_PIN  17
#define GPS_BAUD    9600

#define SD_SCK_PIN  12
#define SD_MOSI_PIN 11
#define SD_MISO_PIN 13
#define SD_CS_PIN   10

// ── BLE ───────────────────────────────────────────────────────
#define BLE_NAME        "CAR_GOES_VROOM"
#define SERVICE_UUID    "26efde6e-344c-47a4-bf50-78d548220c87"
#define GPS_UUID        "d69584e5-5142-414f-a90e-07c271d18575"
#define IMU_UUID        "d69584e5-5142-414f-a90e-07c271d18576"

// GPS payload:  float lat, float lon, float speed        (12 bytes)
// IMU payload:  float yaw, pitch, roll, ax, ay, az       (24 bytes)

// ── Sample rate ───────────────────────────────────────────────
#define IMU_INTERVAL_US    10000UL   // 100 Hz
#define OUTPUT_INTERVAL_MS 20        // 50 Hz serial/SD/BLE output

// ── Objects ───────────────────────────────────────────────────
Adafruit_BNO08x   imu(-1);
TinyGPSPlus       gps;
HardwareSerial    gpsSerial(1);
SPIClass          sdSPI(HSPI);
File              logFile;
bool              sdOK = false;

NimBLECharacteristic *gpsChar = nullptr;
NimBLECharacteristic *imuChar = nullptr;

// ── IMU state ─────────────────────────────────────────────────
float imu_yaw   = 0.0f;
float imu_pitch = 0.0f;
float imu_roll  = 0.0f;
float imu_ax    = 0.0f;
float imu_ay    = 0.0f;
float imu_az    = 0.0f;

// ── Quaternion → Euler (ZYX, degrees) ────────────────────────
void quatToEuler(float w, float x, float y, float z,
                 float &yaw, float &pitch, float &roll) {
    roll  = degrees(atan2f(2.0f*(w*x + y*z), 1.0f - 2.0f*(x*x + y*y)));
    float sinp = 2.0f*(w*y - z*x);
    pitch = (fabsf(sinp) >= 1.0f) ? copysignf(90.0f, sinp) : degrees(asinf(sinp));
    yaw   = degrees(atan2f(2.0f*(w*z + x*y), 1.0f - 2.0f*(y*y + z*z)));
}

// ── Setup ─────────────────────────────────────────────────────
void setup() {
    delay(500);  // give USB time to enumerate before first print
    Serial.begin(115200);
    uint32_t t0 = millis();
    while (!Serial && millis() - t0 < 4000);  // wait up to 4 s for monitor
    Serial.println("# DAQ starting...");
    Serial.flush();

    // I2C + BNO085
    Serial.println("# Init I2C...");
    Serial.flush();
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setTimeout(1000);  // don't hang forever on stuck bus
    Serial.println("# I2C bus up, probing BNO085...");
    Serial.flush();
    if (!imu.begin_I2C(BNO08x_I2CADDR_DEFAULT, &Wire)) {
        Serial.println("# ERROR: BNO085 not found (addr 0x4A). Check wiring/ADR pin.");
        Serial.flush();
        // continue without IMU rather than halting silently
    } else {
        imu.enableReport(SH2_ROTATION_VECTOR,     IMU_INTERVAL_US);
        imu.enableReport(SH2_LINEAR_ACCELERATION, IMU_INTERVAL_US);
        Serial.println("# BNO085 OK");
    }

    // GPS
    gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
    Serial.println("# GPS UART OK");

    // SD card (optional)
    sdSPI.begin(SD_SCK_PIN, SD_MISO_PIN, SD_MOSI_PIN, SD_CS_PIN);
    if (!SD.begin(SD_CS_PIN, sdSPI)) {
        Serial.println("# WARN: SD card not found – logging to serial only");
    } else {
        char fname[24];
        for (int i = 0; i < 1000; i++) {
            snprintf(fname, sizeof(fname), "/run_%03d.csv", i);
            if (!SD.exists(fname)) break;
        }
        logFile = SD.open(fname, FILE_WRITE);
        if (logFile) {
            sdOK = true;
            Serial.print("# SD OK – logging to ");
            Serial.println(fname);
        } else {
            Serial.println("# WARN: SD found but could not open file");
        }
    }

    // BLE
    NimBLEDevice::init(BLE_NAME);
    NimBLEDevice::setSecurityAuth(false, false, false);
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);

    NimBLEServer  *server  = NimBLEDevice::createServer();
    NimBLEService *service = server->createService(SERVICE_UUID);

    gpsChar = service->createCharacteristic(
        GPS_UUID,
        NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY
    );
    imuChar = service->createCharacteristic(
        IMU_UUID,
        NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY
    );

    service->start();

    NimBLEAdvertising *adv = NimBLEDevice::getAdvertising();
    NimBLEAdvertisementData advData;
    advData.setName(BLE_NAME);
    advData.setFlags(0x06);
    advData.addServiceUUID(service->getUUID());
    adv->setAdvertisementData(advData);
    adv->start();

    Serial.println("# BLE advertising as " BLE_NAME);

    // CSV header
    const char *header = "millis,yaw_deg,pitch_deg,roll_deg,ax_ms2,ay_ms2,az_ms2,"
                         "lat,lon,gps_speed_mps,gps_sats";
    Serial.println(header);
    if (sdOK) { logFile.println(header); logFile.flush(); }
}

// ── Loop ──────────────────────────────────────────────────────
void loop() {
    // Feed GPS bytes to parser
    while (gpsSerial.available()) {
        gps.encode(gpsSerial.read());
    }

    // Poll BNO085
    sh2_SensorValue_t sv;
    if (imu.getSensorEvent(&sv)) {
        switch (sv.sensorId) {
            case SH2_ROTATION_VECTOR: {
                auto &rv = sv.un.rotationVector;
                quatToEuler(rv.real, rv.i, rv.j, rv.k,
                            imu_yaw, imu_pitch, imu_roll);
                break;
            }
            case SH2_LINEAR_ACCELERATION: {
                imu_ax = sv.un.linearAcceleration.x;
                imu_ay = sv.un.linearAcceleration.y;
                imu_az = sv.un.linearAcceleration.z;
                break;
            }
        }
    }

    // Output at 50 Hz
    static uint32_t lastOut = 0;
    uint32_t now = millis();
    if (now - lastOut < OUTPUT_INTERVAL_MS) return;
    lastOut = now;

    double lat   = gps.location.isValid()   ? gps.location.lat()         : 0.0;
    double lon   = gps.location.isValid()   ? gps.location.lng()         : 0.0;
    float  speed = gps.speed.isValid()      ? (float)gps.speed.mps()     : 0.0f;
    int    sats  = gps.satellites.isValid() ? (int)gps.satellites.value(): 0;

    // Serial + SD
    char row[128];
    snprintf(row, sizeof(row),
             "%lu,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.7f,%.7f,%.3f,%d",
             now,
             imu_yaw, imu_pitch, imu_roll,
             imu_ax, imu_ay, imu_az,
             lat, lon, speed, sats);
    Serial.println(row);
    if (sdOK && logFile) { logFile.println(row); logFile.flush(); }

    // BLE – GPS characteristic: lat, lon, speed as floats (12 bytes)
    float gpsPayload[3] = { (float)lat, (float)lon, speed };
    gpsChar->setValue((uint8_t*)gpsPayload, sizeof(gpsPayload));
    gpsChar->notify();

    // BLE – IMU characteristic: yaw, pitch, roll, ax, ay, az (24 bytes)
    float imuPayload[6] = { imu_yaw, imu_pitch, imu_roll,
                            imu_ax,  imu_ay,    imu_az  };
    imuChar->setValue((uint8_t*)imuPayload, sizeof(imuPayload));
    imuChar->notify();
}
