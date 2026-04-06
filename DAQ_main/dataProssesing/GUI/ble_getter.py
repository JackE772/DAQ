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

    @staticmethod
    def _is_connected(client):
        return client is not None and getattr(client, "is_connected", False)

    def is_connected(self):
        return self._is_connected(self.client)

    async def connect(self, logger=None):
        if self.is_connected():
            if logger:
                logger.log_message("BLE client already connected.", level="DEBUG")
            return True

        if logger:
            logger.log_message("Scanning for BLE peripherals...", level="INFO")
        else:
            print("Scanning for BLE peripherals...")
        devices = await BleakScanner.discover()

        target = None
        for d in devices:
            if d.name and "car_go_vroom" in d.name.lower():
                target = d
                if logger:
                    logger.log_message(f"Target peripheral found: {d.name} ({d.address})", level="SUCCESS")
                else:
                    print(f"Target peripheral found: {d.name} ({d.address})")
                break

        if not target:
            if logger:
                logger.log_message("Target peripheral not found during scan.", level="WARN")
            else:
                print("Target peripheral not found during scan.")
            return False

        self.client = BleakClient(target)
        await self.client.connect()
        if logger:
            logger.log_message(
                f"BLE transport connected to {target.name} ({target.address})",
                level="SUCCESS"
            )
        else:
            print(f"Connected to {target.name} ({target.address})")
        return True
    
    async def disconnect(self, logger=None):
        if self.is_connected():
            await self.client.disconnect()
            if logger:
                logger.log_message("BLE transport disconnected.", level="WARN")
            else:
                print("Disconnected from device.")
        self.client = None

    async def read_gps_status(self):
        if self.is_connected():
            gps_data = await self.client.read_gatt_char(self.GPS_STATUS_CHARACTERISTIC_UUID)
            if len(gps_data) < 8:
                return None

            lat, lon = struct.unpack('<ff', gps_data[:8])
            return {
                "lat": lat,
                "lon": lon,
            }
        return None

    async def read_imu_data(self):
        if self.is_connected():
            imu_data = await self.client.read_gatt_char(self.IMU_CHARACTERISTIC_UUID)
            if len(imu_data) < 48:
                return None

            imu_values = struct.unpack('<ffffffffffff', imu_data[:48])
            return {
                "yaw": imu_values[0],
                "roll": imu_values[1],
                "pitch": imu_values[2],
                "ax_b": imu_values[3],
                "ay_b": imu_values[4],
                "az_b": imu_values[5],
                "ax_w": imu_values[6],
                "ay_w": imu_values[7],
                "vx": imu_values[8],
                "vy": imu_values[9],
                "x": imu_values[10],
                "y": imu_values[11],
            }
        return None