import asyncio
import struct
from datetime import datetime
from bleak import BleakScanner, BleakClient
import sys

class DataGetter:
    DEVICE_ADDRESS = "CAR_GO_VROOM"

    CURRENT_TIME_CHARACTERISTIC_UUID = "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1c"
    GPS_STATUS_CHARACTERISTIC_UUID   = "d69584e5-5142-414f-a90e-07c271d18575"
    IMU_CHARACTERISTIC_UUID          = "d69584e5-5142-414f-a90e-07c271d18576"

    def __init__(self):
        self.client = None

    async def connect(self):
        print("Scanning for ESP32 BLE device...")
        devices = await BleakScanner.discover()

        target = None
        for d in devices:
            print(f"Found: {d.name}, {d.address}")
            if d.name and "car_go_vroom" in d.name.lower():
                target = d
                print(f"Target device found: {d.name}, {d.address}")
                break

        if not target:
            print("Could not find ESP32 with name 'CAR_GO_VROOM'")
            return False

        self.client = BleakClient(target)
        await self.client.connect()
        print(f"Connected to {target.name} ({target.address})")
        return True
    
    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
            print("Disconnected from BLE device")

    async def read_gps_status(self):
        if self.client:
            gps_data = await self.client.read_gatt_char(self.GPS_STATUS_CHARACTERISTIC_UUID)
            return gps_data
        return None

    async def read_imu_data(self):
        if self.client:
            imu_data = await self.client.read_gatt_char(self.IMU_CHARACTERISTIC_UUID)
            imu_values = struct.unpack('ffffffffffff', imu_data)
            return imu_values
        return None