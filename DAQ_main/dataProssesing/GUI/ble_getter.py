import asyncio
import struct
from datetime import datetime
from bleak import BleakScanner, BleakClient
import sys
import time

class DataGetter:
    DEVICE_ADDRESS = "CAR_GOES_VROOM"

    CURRENT_TIME_CHARACTERISTIC_UUID = "f4c8e2b3-3d1e-4f3a-8e2e-5f6b8c9d0a1c"
    GPS_STATUS_CHARACTERISTIC_UUID   = "d69584e5-5142-414f-a90e-07c271d18575"
    IMU_CHARACTERISTIC_UUID          = "d69584e5-5142-414f-a90e-07c271d18576"

    def __init__(self):
        self.client = None
        self._last_short_gps_log_s = 0.0
        self._last_short_imu_log_s = 0.0

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
            if d.name and "car_goes_vroom" in d.name.lower():
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

    async def read_gps_status(self, logger=None):
        if self.is_connected():
            gps_data = await self.client.read_gatt_char(self.GPS_STATUS_CHARACTERISTIC_UUID)
            if len(gps_data) < 8:
                now_s = time.monotonic()
                if logger and (now_s - self._last_short_gps_log_s) > 2.0:
                    logger.log_message(
                        f"GPS payload too short: expected 8 bytes, got {len(gps_data)} bytes",
                        level="WARN"
                    )
                    self._last_short_gps_log_s = now_s
                return None

            lat, lon = struct.unpack('<ff', gps_data[:8])
            return {
                "lat": lat,
                "lon": lon,
            }
        return None

    async def read_imu_data(self, logger=None):
        if self.is_connected():
            imu_data = await self.client.read_gatt_char(self.IMU_CHARACTERISTIC_UUID)
            if len(imu_data) < 24:
                now_s = time.monotonic()
                if logger and (now_s - self._last_short_imu_log_s) > 2.0:
                    logger.log_message(
                        f"IMU payload too short: expected 24 bytes, got {len(imu_data)} bytes",
                        level="WARN"
                    )
                    self._last_short_imu_log_s = now_s
                return None

            imu_values = struct.unpack('<ffffff', imu_data[:24])
            return {
                "yaw":   imu_values[0],
                "pitch": imu_values[1],
                "roll":  imu_values[2],
                "ax":    imu_values[3],
                "ay":    imu_values[4],
                "az":    imu_values[5],
            }
        return None