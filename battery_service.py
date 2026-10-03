#!/usr/bin/env python3

from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

LOW_BATTERY_THRESHOLD: int = 20
CRITICAL_BATTERY_THRESHOLD: int = 10

UP_DEVICE_KIND_UNKNOWN = 0
UP_DEVICE_KIND_LINE_POWER = 1
UP_DEVICE_KIND_BATTERY = 2
UP_DEVICE_KIND_UPS = 3
UP_DEVICE_KIND_MONITOR = 4
UP_DEVICE_KIND_MOUSE = 5
UP_DEVICE_KIND_KEYBOARD = 6
UP_DEVICE_KIND_PDA = 7
UP_DEVICE_KIND_PHONE = 8

UP_DEVICE_STATE_UNKNOWN = 0
UP_DEVICE_STATE_CHARGING = 1
UP_DEVICE_STATE_DISCHARGING = 2
UP_DEVICE_STATE_EMPTY = 3
UP_DEVICE_STATE_FULLY_CHARGED = 4
UP_DEVICE_STATE_PENDING_CHARGE = 5
UP_DEVICE_STATE_PENDING_DISCHARGE = 6

def _query_upower_dbus() -> Optional[tuple[bool, int, bool]]:
    try:
        import dbus
    except ImportError:
        return None

    try:
        bus = dbus.SystemBus()
        up_obj = bus.get_object("org.freedesktop.UPower", "/org/freedesktop/UPower")
        up_props = dbus.Interface(up_obj, "org.freedesktop.DBus.Properties")

        try:
            on_battery = bool(up_props.Get("org.freedesktop.UPower", "OnBattery"))
        except Exception:
            on_battery = False

        try:
            disp_obj = bus.get_object("org.freedesktop.UPower", "/org/freedesktop/UPower/devices/DisplayDevice")
            disp_props = dbus.Interface(disp_obj, "org.freedesktop.DBus.Properties")
            dev_type = int(disp_props.Get("org.freedesktop.UPower.Device", "Type"))
            is_present = bool(disp_props.Get("org.freedesktop.UPower.Device", "IsPresent"))
            power_supply = bool(disp_props.Get("org.freedesktop.UPower.Device", "PowerSupply"))

            if dev_type == UP_DEVICE_KIND_BATTERY and (is_present or power_supply):
                pct = int(round(float(disp_props.Get("org.freedesktop.UPower.Device", "Percentage"))))
                state = int(disp_props.Get("org.freedesktop.UPower.Device", "State"))
                is_plugged = (state in (UP_DEVICE_STATE_CHARGING, UP_DEVICE_STATE_FULLY_CHARGED, UP_DEVICE_STATE_PENDING_CHARGE)) or (not on_battery)
                return True, max(0, min(100, pct)), is_plugged
        except Exception:
            pass

        try:
            up_iface = dbus.Interface(up_obj, "org.freedesktop.UPower")
            dev_paths = up_iface.EnumerateDevices()
            for dev_path in dev_paths:
                try:
                    dev = bus.get_object("org.freedesktop.UPower", dev_path)
                    props_iface = dbus.Interface(dev, "org.freedesktop.DBus.Properties")
                    p = props_iface.GetAll("org.freedesktop.UPower.Device")
                    d_type = int(p.get("Type", 0))
                    d_ps = bool(p.get("PowerSupply", 0))
                    d_pres = bool(p.get("IsPresent", 0))

                    if d_type == UP_DEVICE_KIND_BATTERY and (d_ps or d_pres):
                        pct = int(round(float(p.get("Percentage", 0.0))))
                        state = int(p.get("State", 0))
                        is_plugged = (state in (UP_DEVICE_STATE_CHARGING, UP_DEVICE_STATE_FULLY_CHARGED, UP_DEVICE_STATE_PENDING_CHARGE)) or (not on_battery)
                        return True, max(0, min(100, pct)), is_plugged
                except Exception:
                    continue
        except Exception:
            pass

        return False, 0, not on_battery

    except Exception as e:
        logger.debug("UPower D-Bus query error: %s", e)
        return None

def _query_sysfs() -> Optional[tuple[bool, int, bool]]:
    bat_dirs = sorted(glob.glob("/sys/class/power_supply/BAT*"))
    if not bat_dirs:
        ac_dirs = glob.glob("/sys/class/power_supply/AC*") + glob.glob("/sys/class/power_supply/ADP*")
        if ac_dirs:
            return False, 0, True
        return None

    ac_online: Optional[bool] = None
    for ac_path in glob.glob("/sys/class/power_supply/AC*") + glob.glob("/sys/class/power_supply/ADP*") + glob.glob("/sys/class/power_supply/*mains*"):
        try:
            with open(os.path.join(ac_path, "online"), "r") as f:
                ac_online = (f.read().strip() == "1")
                break
        except Exception:
            pass

    for bat_path in bat_dirs:
        try:
            pres_file = os.path.join(bat_path, "present")
            if os.path.isfile(pres_file):
                with open(pres_file, "r") as f:
                    if f.read().strip() == "0":
                        continue

            cap_file = os.path.join(bat_path, "capacity")
            if not os.path.isfile(cap_file):
                continue
            with open(cap_file, "r") as f:
                percent = int(f.read().strip())

            status = ""
            status_file = os.path.join(bat_path, "status")
            if os.path.isfile(status_file):
                with open(status_file, "r") as f:
                    status = f.read().strip().lower()

            is_charging = status in ("charging", "full", "not charging")
            is_plugged = (ac_online is True) or is_charging if ac_online is not None else is_charging

            return True, max(0, min(100, percent)), is_plugged
        except Exception as e:
            logger.debug("Failed reading sysfs battery %s: %s", bat_path, e)

    return False, 0, True

def _query_upower_cli() -> Optional[tuple[bool, int, bool]]:
    if not shutil.which("upower"):
        return None

    try:
        res = subprocess.run(
            ["upower", "-d"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        if res.returncode != 0 or not res.stdout:
            return None

        on_battery_match = re.search(r"on-battery:\s*(yes|no)", res.stdout, re.IGNORECASE)
        on_battery = on_battery_match.group(1).lower() == "yes" if on_battery_match else False

        sections = res.stdout.split("Device:")
        for sec in sections:
            sec_lower = sec.lower()
            if "battery" not in sec_lower or "percentage:" not in sec_lower:
                continue

            pct_m = re.search(r"percentage:\s*([0-9.]+)%", sec)
            if not pct_m:
                continue
            pct = int(round(float(pct_m.group(1))))

            state_m = re.search(r"state:\s*([a-z-]+)", sec_lower)
            state_str = state_m.group(1) if state_m else ""
            is_plugged = (state_str in ("charging", "fully-charged", "pending-charge")) or (not on_battery)

            return True, max(0, min(100, pct)), is_plugged

        return False, 0, not on_battery

    except Exception as e:
        logger.debug("upower CLI battery query error: %s", e)
        return None

def get_power_status() -> tuple[bool, int, bool]:
    res = _query_upower_dbus()
    if res is not None:
        return res

    res = _query_sysfs()
    if res is not None:
        return res

    res = _query_upower_cli()
    if res is not None:
        return res

    return False, 0, True

def try_get_battery() -> tuple[bool, int, bool]:
    return get_power_status()

class BatteryService:

    def __init__(
        self,
        on_power_changed: Optional[Callable[[bool, int, bool], None]] = None,
        on_charge_started: Optional[Callable[[int], None]] = None,
        on_charge_stopped: Optional[Callable[[int], None]] = None,
        on_low_battery: Optional[Callable[[int, int], None]] = None,
        poll_interval: float = 2.0,
        auto_start: bool = True,
    ) -> None:
        self.poll_interval = max(0.5, float(poll_interval))
        self._lock = threading.RLock()

        self.on_power_changed = on_power_changed
        self.on_charge_started = on_charge_started
        self.on_charge_stopped = on_charge_stopped
        self.on_low_battery = on_low_battery

        self._power_changed_listeners: list[Callable[[bool, int, bool], None]] = []
        if on_power_changed:
            self._power_changed_listeners.append(on_power_changed)

        self._simulated: Optional[tuple[bool, int, bool]] = None
        has_bat, pct, plugged = self.get_power_status()
        self._has_battery: bool = has_bat
        self._percent: int = pct
        self._plugged: bool = plugged
        self._known: bool = False

        self._running: bool = False
        self._monitor_thread: Optional[threading.Thread] = None

        if auto_start:
            self.start()

    def get_power_status(self) -> tuple[bool, int, bool]:
        with self._lock:
            if self._simulated is not None:
                return self._simulated
        return get_power_status()

    def try_get_battery(self) -> tuple[bool, int, bool]:
        return self.get_power_status()

    def add_listener(self, callback: Callable[[bool, int, bool], None]) -> None:
        with self._lock:
            if callback not in self._power_changed_listeners:
                self._power_changed_listeners.append(callback)

    def remove_listener(self, callback: Callable[[bool, int, bool], None]) -> None:
        with self._lock:
            if callback in self._power_changed_listeners:
                self._power_changed_listeners.remove(callback)

    def simulate_power(self, has_battery: bool, percent: int, is_plugged: bool) -> None:
        with self._lock:
            self._simulated = (has_battery, max(0, min(100, percent)), is_plugged)
        self.check_power()

    def clear_simulation(self) -> None:
        with self._lock:
            self._simulated = None
        self.check_power()

    def check_power(self) -> None:
        has_battery, percent, is_plugged = self.get_power_status()

        with self._lock:
            was_known = self._known
            was_battery = self._has_battery
            was_percent = self._percent
            was_plugged = self._plugged

            self._has_battery = has_battery
            self._percent = percent
            self._plugged = is_plugged
            self._known = True

            listeners = list(self._power_changed_listeners)
            cb_started = self.on_charge_started
            cb_stopped = self.on_charge_stopped
            cb_low = self.on_low_battery

        if was_known and has_battery:
            if is_plugged and not was_plugged:
                logger.info("AC adapter plugged in (charge started at %d%%)", percent)
                if cb_started:
                    try:
                        cb_started(percent)
                    except Exception as e:
                        logger.error("Error in on_charge_started: %s", e)

            elif not is_plugged and was_plugged:
                logger.info("AC adapter unplugged (battery at %d%%)", percent)
                if cb_stopped:
                    try:
                        cb_stopped(percent)
                    except Exception as e:
                        logger.error("Error in on_charge_stopped: %s", e)

            if not is_plugged:
                if was_percent > LOW_BATTERY_THRESHOLD >= percent:
                    logger.warning("Low battery warning: %d%%", percent)
                    if cb_low:
                        try:
                            cb_low(LOW_BATTERY_THRESHOLD, percent)
                        except Exception as e:
                            logger.error("Error in on_low_battery: %s", e)

                elif was_percent > CRITICAL_BATTERY_THRESHOLD >= percent:
                    logger.critical("Critical battery alert: %d%%", percent)
                    if cb_low:
                        try:
                            cb_low(CRITICAL_BATTERY_THRESHOLD, percent)
                        except Exception as e:
                            logger.error("Error in on_low_battery: %s", e)

        if not was_known or (was_battery, was_percent, was_plugged) != (has_battery, percent, is_plugged):
            for listener in listeners:
                try:
                    listener(has_battery, percent, is_plugged)
                except Exception as e:
                    logger.error("Error in power changed listener: %s", e)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._monitor_thread = threading.Thread(
            target=self._monitor_worker,
            daemon=True,
            name="BatteryServiceMonitor",
        )
        self._monitor_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _monitor_worker(self) -> None:
        while self._running:
            try:
                self.check_power()
            except Exception as e:
                logger.debug("Error during battery status check: %s", e)
            time.sleep(self.poll_interval)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("DynamicIsland Linux - BatteryService Test")
    print("=" * 60)

    has_bat, pct, plugged = get_power_status()
    print(f"Has Battery : {has_bat}")
    print(f"Percentage  : {pct}%")
    print(f"AC Plugged  : {plugged}")

    events: list[str] = []

    def handle_power_changed(has_b: bool, p: int, plug: bool) -> None:
        events.append(f"power_changed(has_bat={has_b}, pct={p}%, plugged={plug})")

    def handle_charge_started(p: int) -> None:
        events.append(f"CHARGE_TOAST: Started charging at {p}% ⚡")

    def handle_charge_stopped(p: int) -> None:
        events.append(f"UNPLUGGED: Running on battery at {p}%")

    def handle_low_battery(thresh: int, p: int) -> None:
        events.append(f"LOW_BATTERY_ALERT: Passed threshold {thresh}% (current: {p}%)")

    service = BatteryService(
        on_power_changed=handle_power_changed,
        on_charge_started=handle_charge_started,
        on_charge_stopped=handle_charge_stopped,
        on_low_battery=handle_low_battery,
        auto_start=False,
    )

    print("\nInitial Service Status:", service.get_power_status())
    print("\nTesting simulation: Discharging to 22%...")
    service.simulate_power(has_battery=True, percent=22, is_plugged=False)

    print("Testing simulation: Crossing low battery threshold to 19%...")
    service.simulate_power(has_battery=True, percent=19, is_plugged=False)

    print("Testing simulation: AC plugged in at 19% (triggers dynamic Charge toast)...")
    service.simulate_power(has_battery=True, percent=19, is_plugged=True)

    print("\nCaptured events:")
    for ev in events:
        print(f"  • {ev}")

    service.clear_simulation()
    service.stop()
    print("=" * 60)
