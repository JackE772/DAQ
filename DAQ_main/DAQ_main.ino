#include <Adafruit_BNO055.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <TinyGPS.h>

int pot_1 = 0;
int pot_2 = 0;

//for reading from adafruit IMU
double xPos = 0, yPos = 0, headingVel = 0;
uint16_t BNO055_SAMPLERATE_DELAY_MS = 10; //how often to read data from the board. this was in test code idk if we need it

double ACCEL_VEL_TRANSITION =  (double)(BNO055_SAMPLERATE_DELAY_MS) / 1000.0;
double ACCEL_POS_TRANSITION = 0.5 * ACCEL_VEL_TRANSITION * ACCEL_VEL_TRANSITION;
double DEG_2_RAD = 0.01745329251; //trig functions require radians, BNO055 outputs degrees

// Check I2C device address and correct line below (by default address is 0x29 or 0x28)
//                                   id, address
Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28);


void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);

  while (!Serial) delay(10);  // wait for serial port to open!

  if (!bno.begin()) //abort if IMU not detected
  {
    Serial.println("No BNO055 detected");
    while (1);
  }

  pinMode(A2, INPUT);
  pinMode(A3, INPUT);
}


void loop() {
  // put your main code here, to run repeatedly:

  logImuData();
  Serial.print(",");
  logPotentiometerData();
  Serial.println("");
  // test();
  
}

void logImuData(){
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

  // heading CH1
  Serial.print(orientationData.orientation.x);
  Serial.print(",");
  // position X CH2
  Serial.print(xPos);
  Serial.print(" , ");
  // position Y CH3
  Serial.print(yPos);
  Serial.print(" , ");
  // speed CH4
  Serial.print(headingVel);
}

void logPotentiometerData(){
  pot_1 = analogRead(A0);
  pot_2 = analogRead(A1);
  // Pot_1 reading CH5
  Serial.print(pot_1);
  Serial.print(" , ");
  // Pot_2 reading CH6
  Serial.print(pot_2);
}

//for testing data loging with two CH :
void test(){
  Serial.print("1");
  Serial.print(" , ");
  Serial.println("2");

  Serial.print("3");
  Serial.print(" , ");
  Serial.println("4");
}