import asyncio
import struct
from datetime import datetime
from bleak import BleakScanner, BleakClient

#ID of the BLE device  (set in ESP32 code)
DEVICE_ADDRESS = "CAR_GO_VROOM"

# Useing a custom characteristic UUID that your ESP32 exposes as writable
# (don't use 0x2A2B as it's read-only)
CURRENT_TIME_CHARACTERISTIC_UUID = "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1c"
GPS_STATUS_CHARACTERISTIC_UUID   = "d69584e5-5142-414f-a90e-07c271d18575"



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
            data = await client.read_gatt_char(GPS_STATUS_CHARACTERISTIC_UUID)
            gps_status = int(data[0])  # convert from single byte to int (0 or 1)
            print(gps_status)
            if gps_status:
                print("GPS has a fix")
            else:
                print("No GPS fix")

            await asyncio.sleep(2)  # poll every 2 seconds
if __name__ == "__main__":
    asyncio.run(main())