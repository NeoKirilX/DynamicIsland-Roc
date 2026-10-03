#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

BLUETOOTH_AUDIO_UUIDS = {
    "0000110b-0000-1000-8000-00805f9b34fb",
    "00001108-0000-1000-8000-00805f9b34fb",
    "0000111e-0000-1000-8000-00805f9b34fb",
}

UPOWER_AUDIO_DEVICE_TYPES = {17, 18, 19, 20}

def _is_audio_device(props: dict) -> bool:
    icon = str(props.get("Icon", "")).lower()
    if any(k in icon for k in ("headphone", "headset", "audio")):
        return True

    dev_class = props.get("Class")
    if isinstance(dev_class, int) and ((dev_class >> 8) & 0x1F) == 4:
        return True

    uuids = {str(u).lower() for u in props.get("UUIDs", [])}
    if any(u.lower() in uuids for u in BLUETOOTH_AUDIO_UUIDS):
        return True

    name = f"{props.get('Name', '')} {props.get('Alias', '')}".lower()
    keywords = ("headphone", "headset", "earphone", "earbuds", "airpods", "buds", "wh-", "wf-")
    if any(k in name for k in keywords):
        return True

    return False

def _matches_target(path: str, dev_props: dict, target_device: Optional[str]) -> bool:
    if not target_device:
        return True

    target_norm = target_device.strip().lower()
    mac_norm = target_norm.replace(":", "_").replace("-", "_")

    path_lower = path.lower()
    addr_lower = str(dev_props.get("Address", "")).lower().replace(":", "_")
    name_lower = str(dev_props.get("Name", "")).lower()
    alias_lower = str(dev_props.get("Alias", "")).lower()

    return (
        mac_norm in path_lower
        or mac_norm == addr_lower
        or target_norm in name_lower
        or target_norm in alias_lower
    )

def get_bluez_headset_charge(target_device: Optional[str] = None) -> int:
    try:
        import dbus
    except ImportError:
        logger.debug("dbus-python not installed; skipping BlueZ D-Bus query")
        return -1

    try:
        bus = dbus.SystemBus()
        bluez_obj = bus.get_object("org.bluez", "/")
        mgr = dbus.Interface(bluez_obj, "org.freedesktop.DBus.ObjectManager")
        objects = mgr.GetManagedObjects()

        audio_candidates: list[tuple[int, int]] = []

        for path, interfaces in objects.items():
            if "org.bluez.Battery1" not in interfaces:
                continue

            dev_props = interfaces.get("org.bluez.Device1", {})

            if dev_props and not dev_props.get("Connected", True):
                continue

            if not _matches_target(str(path), dev_props, target_device):
                continue

            pct_val = interfaces["org.bluez.Battery1"].get("Percentage")
            if pct_val is None:
                continue
            pct = int(pct_val)
            if not (0 <= pct <= 100):
                continue

            is_audio = _is_audio_device(dev_props)
            priority = 2 if is_audio else 1
            audio_candidates.append((priority, pct))

        if audio_candidates:
            audio_candidates.sort(key=lambda x: x[0], reverse=True)
            return audio_candidates[0][1]

    except Exception as e:
        logger.debug("BlueZ D-Bus battery query failed: %s", e)

    return -1

def get_upower_headset_charge(target_device: Optional[str] = None) -> int:
    try:
        import dbus
        bus = dbus.SystemBus()
        upower_obj = bus.get_object("org.freedesktop.UPower", "/org/freedesktop/UPower")
        devices = upower_obj.EnumerateDevices(dbus_interface="org.freedesktop.UPower")

        for dev_path in devices:
            dev = bus.get_object("org.freedesktop.UPower", dev_path)
            props_iface = dbus.Interface(dev, "org.freedesktop.DBus.Properties")
            props = props_iface.GetAll("org.freedesktop.UPower.Device")

            dev_type = int(props.get("Type", 0))
            path_str = str(dev_path).lower()
            model = str(props.get("Model", "")).lower()

            is_headset = (
                dev_type in UPOWER_AUDIO_DEVICE_TYPES
                or "headset" in path_str
                or "headphone" in path_str
                or any(k in model for k in ("headphone", "headset", "earbuds", "buds"))
            )

            if not is_headset:
                continue

            if target_device:
                tgt = target_device.lower()
                if tgt not in path_str and tgt not in model:
                    continue

            pct = props.get("Percentage")
            if pct is not None and 0 <= float(pct) <= 100:
                return int(round(float(pct)))

    except Exception as e:
        logger.debug("UPower D-Bus battery query failed: %s", e)

    if shutil.which("upower"):
        try:
            res = subprocess.run(
                ["upower", "-e"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    dev_path = line.strip()
                    if not dev_path:
                        continue
                    path_lower = dev_path.lower()
                    if any(k in path_lower for k in ("headset", "headphone", "audio")):
                        info = subprocess.run(
                            ["upower", "-i", dev_path],
                            capture_output=True,
                            text=True,
                            timeout=2.0,
                            check=False,
                        )
                        if info.returncode == 0 and info.stdout:
                            match = re.search(r"percentage:\s*([0-9.]+)\s*%", info.stdout, re.IGNORECASE)
                            if match:
                                return int(round(float(match.group(1))))
        except Exception as e:
            logger.debug("UPower CLI battery query failed: %s", e)

    return -1

def get_headset_charge(target_device: Optional[str] = None) -> int:
    charge = get_bluez_headset_charge(target_device)
    if charge >= 0:
        return charge

    charge = get_upower_headset_charge(target_device)
    if charge >= 0:
        return charge

    return -1

def get_charge(target_device: Optional[str] = None) -> int:
    return get_headset_charge(target_device)

class Headset:

    @staticmethod
    def charge(device: Optional[str] = None) -> int:
        return get_headset_charge(device)

    @staticmethod
    async def charge_async(device: Optional[str] = None) -> int:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_headset_charge, device)

if __name__ == "__main__":
    from unittest.mock import MagicMock, patch

    print("=== Testing Headset Battery Service (Linux BlueZ / UPower) ===")

    print("[Live Query] Checking connected Bluetooth headset battery...")
    live_charge = get_headset_charge()
    if live_charge >= 0:
        print(f"  -> Connected headset battery: {live_charge}%")
    else:
        print("  -> No Bluetooth headset battery reported (-1: wired, disconnected, or no BT hardware).")

    print("[Unit Test] Simulating BlueZ Battery1 D-Bus device (Sony WH-1000XM4 @ 85%)...")
    mock_bus = MagicMock()
    mock_mgr = MagicMock()
    mock_mgr.GetManagedObjects.return_value = {
        "/org/bluez/hci0/dev_38_18_4C_AA_BB_CC": {
            "org.bluez.Device1": {
                "Address": "38:18:4C:AA:BB:CC",
                "Name": "WH-1000XM4",
                "Alias": "WH-1000XM4",
                "Connected": True,
                "Icon": "audio-headset",
                "Class": 0x240404,
                "UUIDs": ["0000110b-0000-1000-8000-00805f9b34fb"],
            },
            "org.bluez.Battery1": {
                "Percentage": 85,
            },
        }
    }
    mock_bus.get_object.return_value = MagicMock()

    with patch("dbus.SystemBus", return_value=mock_bus):
        with patch("dbus.Interface", return_value=mock_mgr):
            test_val = get_bluez_headset_charge()
            assert test_val == 85, f"Expected 85%, got {test_val}"
            print(f"  -> Successfully parsed simulated BlueZ battery: {test_val}%")

            test_filtered = get_bluez_headset_charge("38:18:4C:AA:BB:CC")
            assert test_filtered == 85
            test_mismatch = get_bluez_headset_charge("11:22:33:44:55:66")
            assert test_mismatch == -1
            print("  -> MAC address filtering verified successfully")

    print("[Unit Test] Simulating UPower D-Bus fallback headset (@ 62%)...")
    mock_upower_bus = MagicMock()
    mock_upower_obj = MagicMock()
    mock_upower_obj.EnumerateDevices.return_value = [
        "/org/freedesktop/UPower/devices/headset_dev_00_11_22_33_44_55"
    ]
    mock_dev_obj = MagicMock()
    mock_props_iface = MagicMock()
    mock_props_iface.GetAll.return_value = {
        "Type": 17,
        "Model": "Bose QC45",
        "Percentage": 62.0,
        "IsPresent": True,
    }
    mock_upower_bus.get_object.side_effect = lambda bus_name, path: (
        mock_upower_obj if path == "/org/freedesktop/UPower" else mock_dev_obj
    )

    with patch("dbus.SystemBus", return_value=mock_upower_bus):
        with patch("dbus.Interface", return_value=mock_props_iface):
            upower_val = get_upower_headset_charge()
            assert upower_val == 62, f"Expected 62%, got {upower_val}"
            print(f"  -> Successfully parsed simulated UPower battery: {upower_val}%")

    print("[Unit Test] Testing Headset.charge_async API...")
    async def test_async():
        res = await Headset.charge_async()
        assert isinstance(res, int)
        print(f"  -> Headset.charge_async() returned: {res}")

    asyncio.run(test_async())

    print("=== Headset service tests passed successfully! ===")
