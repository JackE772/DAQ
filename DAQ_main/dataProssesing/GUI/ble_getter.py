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

    async def connect(self, logger=None):
        if logger:
            logger.log_message("Scanning for ESP32 BLE device...")
        else:
            print("Scanning for ESP32 BLE device...")
        devices = await BleakScanner.discover()

        target = None
        for d in devices:
            if logger:
                logger.log_message(f"Found device: {d.name} ({d.address})")
            else:
                print(f"Found device: {d.name} ({d.address})")
            if d.name and "car_go_vroom" in d.name.lower():
                target = d
                if logger:
                    logger.log_message(f"Found target device: {d.name} ({d.address})")
                else:
                    print(f"Found target device: {d.name} ({d.address})")
                break

        if not target:
            if logger:
                logger.log_message("Target device not found.")
            else:
                print("Target device not found.")
            return False

        self.client = BleakClient(target)
        await self.client.connect()
        if logger:
            logger.log_message(f"Connected to {target.name} ({target.address})")
        else:
            print(f"Connected to {target.name} ({target.address})")
        return True
    
    async def disconnect(self, logger=None):
        if self.client:
            await self.client.disconnect()
            if logger:
                logger.log_message("Disconnected from device.")
            else:
                print("Disconnected from device.")

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