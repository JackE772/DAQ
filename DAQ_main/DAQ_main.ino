//#include <SoftwareSerial.h>
#include <HardwareSerial.h>
#include <Adafruit_BNO055.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <TinyGPS.h>
#include <ArduinoBLE.h>
#include <SPI.h>
#include <SD.h>

//adafruit metor does not use defalut SD card pins so I need to set them custom
#define SD_SCK 39
#define SD_MOSI 42
#define SD_MOSO 21
#define SD_CS 45

//UUIDs for bluetooth
#define SERVICE_UUID        "26efde6e-344c-47a4-bf50-78d548220c87"
#define REQUEST_UUID        "d69584e5-5142-414f-a90e-07c271d18574" //
#define RESPONSE_UUID       "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1b" //might use for passing data back and forth idk at this point
#define TIMER_UUID          "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1c"

SPIClass spi = SPIClass(SPI);

int pot_1 = 0;
int pot_2 = 0;

//for reading from adafruit IMU
double xPos = 0, yPos = 0, zPos = 0, headingVel = 0;
uint16_t BNO055_SAMPLERATE_DELAY_MS = 10; //how often to read data from the board. this was in test code idk if we need it
double ACCEL_VEL_TRANSITION =  (double)(BNO055_SAMPLERATE_DELAY_MS) / 1000.0;
double ACCEL_POS_TRANSITION = 0.5 * ACCEL_VEL_TRANSITION * ACCEL_VEL_TRANSITION;
double DEG_2_RAD = 0.01745329251; //trig functions require radians, BNO055 outputs degrees

String line; //output to write to file :)
String line2;
// Check I2C device address and correct line below (by default address is 0x29 or 0x28)
//                                   id, address
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);
HardwareSerial MySerial(2);  // UART2 //time logging

TinyGPS gps;
File logfile;

BLEService wifiService(SERVICE_UUID);
BLECharacteristic requestCharacteristic(REQUEST_UUID, BLEWrite, 32);
BLECharacteristic responseCharacteristic(RESPONSE_UUID, BLERead | BLENotify, 2048);
BLECharacteristic timerCharacteristic(TIMER_UUID, BLERead, 32);


void setup() {
  // logging data on the 9600 band
  Serial.begin(9600);
  // We are usnig a 9600 baud GPS DO NOT CHANGE THE MAGIC NUMBER  
  //ss.begin(9600);//ESP32 does not have software serial need to swap to UART for coms
  // baud rate, config, RX pin, TX pin
  MySerial.begin(9600, SERIAL_8N1, 18, 1); 
  // Initialize custom SPI pins for SD card
  spi.begin(SD_SCK, SD_MOSO, SD_MOSI, SD_CS);  // SCK, MISO, MOSI, SS
  
  delay(2000);//give serial time to init

  if (!bno.begin()) //abort if IMU not detected
  {
    Serial.println("No BNO055 detected");
    while (1);
  }

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

  BLE.setLocalName("CAR_GO_VROOM");
  BLE.setAdvertisedService(wifiService);
  wifiService.addCharacteristic(requestCharacteristic);
  wifiService.addCharacteristic(responseCharacteristic);
  wifiService.addCharacteristic(timerCharacteristic);
  BLE.addService(wifiService);
  BLE.setEventHandler(BLEDisconnected, onCentralDisconnected);
  BLE.advertise();
}


void loop() {
  line = "";
  line2 = ""; //need two line vars bc we run out of ram on the board

  line += logImuData();
  line += ",";

  while (MySerial.available()) {
    gps.encode(MySerial.read());
  }

  line2 += logGPSData();
  line2 += ",";
  line2 += String(millis());
  Serial.print(line);
  Serial.println(line2);
  
  logfile.print(line);
  logfile.println(line2);
  logfile.flush();
}

String logImuData(){
  String result;
  unsigned long tStart = micros();
  sensors_event_t orientationData, linearAccelData;
  bno.getEvent(&orientationData, Adafruit_BNO055::VECTOR_EULER);
  //  bno.getEvent(&angVelData, Adafruit_BNO055::VECTOR_GYROSCOPE);
  bno.getEvent(&linearAccelData, Adafruit_BNO055::VECTOR_LINEARACCEL);

  // new x = x + delta x
  xPos = xPos + ACCEL_POS_TRANSITION * linearAccelData.acceleration.x;
  yPos = yPos + ACCEL_POS_TRANSITION * linearAccelData.acceleration.y;

  // velocity of sensor in the direction it's facing
  headingVel = ACCEL_VEL_TRANSITION * linearAccelData.acceleration.x / cos(DEG_2_RAD * orientationData.orientation.x);

  result += String(orientationData.orientation.x, 6);
  result += ",";
  result += String(orientationData.orientation.y, 6);
  result += ",";
  result += String(orientationData.orientation.z, 6);
  result += ",";
  result += String(xPos, 5);
  result += ",";
  result += String(yPos, 5);
  result += ",";
  result += String(headingVel, 5);
  return result;
}

String logGPSData(){
  float flat, flon;
    unsigned long age;
    gps.f_get_position(&flat, &flon, &age);
    if (flat == TinyGPS::GPS_INVALID_F_ANGLE) flat = 0.0;
    if (flon == TinyGPS::GPS_INVALID_F_ANGLE) flon = 0.0;
    String result = String(flat, 6);
    result += ",";
    result += String(flon, 6);

    return result;
}

void onCentralDisconnected(BLEDevice central) {
    Serial.println("Central disconnected");
    Serial.println("Shutting down BLE");
}