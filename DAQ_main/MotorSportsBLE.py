import asyncio
import struct
from datetime import datetime
from bleak import BleakScanner, BleakClient
import sys

#ID of the BLE device  (set in ESP32 code)
DEVICE_ADDRESS = "CAR_GO_VROOM"

# Useing custom characteristic UUID from ESP32 code
CURRENT_TIME_CHARACTERISTIC_UUID = "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1c"
GPS_STATUS_CHARACTERISTIC_UUID   = "d69584e5-5142-414f-a90e-07c271d18575"
IMU_CHARACTERISTIC_UUID          = "d69584e5-5142-414f-a90e-07c271d18576"



async def main():
    print("Scanning for ESP32 BLE device...")
    devices = await BleakScanner.discover()

    target = None
    for d in devices:
        print(f"Found: {d.name}, {d.address}")
        # Check if the device name contains "washr" (case-insensitive)
        if d.name and "car_go_vroom" in d.name.lower():
            target = d
            print(f"Target device found: {d.name}, {d.address}")
            break

    if not target:
        print("Could not find ESP32 with name 'CAR_GO_VROOM'")
        return

    async with BleakClient(target) as client:
        print(f"Connected to {target.name} ({target.address})")

        print(f"Connected to {target.name}")

        while True:
            # read the GPS status characteristic
            gps_data = await client.read_gatt_char(GPS_STATUS_CHARACTERISTIC_UUID)
            print(datetime.now().strftime("%H:%M:%S"))
            print(f"Latitude: {gps_data[0]}, Longitude: {gps_data[1]}")
            if(gps_data != int(0)):
                print("GPS has a fix")
            else:
                print("No GPS fix")

            # read the IMU characteristic
            imu_data = await client.read_gatt_char(IMU_CHARACTERISTIC_UUID)

            # Unpack the binary data into floats (assuming 12 floats: ex, ey, ez, lx, ly, lz, ax_w, ay_w,  vx, vy, xPos, yPos)
            imu_values = struct.unpack('ffffffffffff', imu_data)
            
            print(f"IMU Data - ex: {imu_values[0]}, ey: {imu_values[1]}, ez: {imu_values[2]}, lx: {imu_values[3]}, ly: {imu_values[4]}, lz: {imu_values[5]}, ax_w: {imu_values[6]}, ay_w: {imu_values[7]}, vx: {imu_values[8]}, vy: {imu_values[9]}, xPos: {imu_values[10]}, yPos: {imu_values[11]}")
            
            await asyncio.sleep(0.5)  # poll every 0.5 seconds
if __name__ == "__main__":
    asyncio.run(main())