#include <Wire.h>

#define I2C_SDA  8
#define I2C_SCL  9

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000);
    Wire.begin(I2C_SDA, I2C_SCL);
    Serial.println("Scanning I2C bus...");

    int found = 0;
    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            Serial.print("Device found at 0x");
            Serial.println(addr, HEX);
            found++;
        }
    }

    if (found == 0) Serial.println("No devices found. Check wiring and power.");
    else Serial.println("Scan complete.");
}

void loop() {}
