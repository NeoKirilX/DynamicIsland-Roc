#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

try:
    from native_wayland import Autostart
except ImportError:
    from .native_wayland import Autostart

logger = logging.getLogger(__name__)

xdg_config = os.environ.get("XDG_CONFIG_HOME")
CONFIG_DIR = (Path(xdg_config) if xdg_config else (Path.home() / ".config")) / "dynamic-island"
CONFIG_FILE = CONFIG_DIR / "settings.json"

xdg_cache = os.environ.get("XDG_CACHE_HOME")
CACHE_DIR = (Path(xdg_cache) if xdg_cache else (Path.home() / ".cache")) / "dynamic-island"

MIN_SCALE = 85
MAX_SCALE = 130
MAX_GAP = 24

class _SettingsMeta(type):

    @property
    def lyrics(cls) -> bool:
        return cls._get_bool("lyrics", True)

    @lyrics.setter
    def lyrics(cls, value: bool) -> None:
        cls._set("lyrics", bool(value))

    @property
    def Lyrics(cls) -> bool:
        return cls.lyrics

    @Lyrics.setter
    def Lyrics(cls, value: bool) -> None:
        cls.lyrics = value

    @property
    def lyric_effects(cls) -> bool:
        return cls._get_bool("lyric_effects", True)

    @lyric_effects.setter
    def lyric_effects(cls, value: bool) -> None:
        cls._set("lyric_effects", bool(value))

    @property
    def LyricEffects(cls) -> bool:
        return cls.lyric_effects

    @LyricEffects.setter
    def LyricEffects(cls, value: bool) -> None:
        cls.lyric_effects = value

    @property
    def rim(cls) -> bool:
        return cls._get_bool("rim", True)

    @rim.setter
    def rim(cls, value: bool) -> None:
        cls._set("rim", bool(value))

    @property
    def Rim(cls) -> bool:
        return cls.rim

    @Rim.setter
    def Rim(cls, value: bool) -> None:
        cls.rim = value

    @property
    def app_volume(cls) -> bool:
        return cls._get_bool("app_volume", True)

    @app_volume.setter
    def app_volume(cls, value: bool) -> None:
        cls._set("app_volume", bool(value))

    @property
    def AppVolume(cls) -> bool:
        return cls.app_volume

    @AppVolume.setter
    def AppVolume(cls, value: bool) -> None:
        cls.app_volume = value

    @property
    def network(cls) -> bool:
        return cls._get_bool("network", True)

    @network.setter
    def network(cls, value: bool) -> None:
        cls._set("network", bool(value))

    @property
    def Network(cls) -> bool:
        return cls.network

    @Network.setter
    def Network(cls, value: bool) -> None:
        cls.network = value

    @property
    def hide_fullscreen(cls) -> bool:
        return cls._get_bool("hide_fullscreen", True)

    @hide_fullscreen.setter
    def hide_fullscreen(cls, value: bool) -> None:
        cls._set("hide_fullscreen", bool(value))

    @property
    def HideFullscreen(cls) -> bool:
        return cls.hide_fullscreen

    @HideFullscreen.setter
    def HideFullscreen(cls, value: bool) -> None:
        cls.hide_fullscreen = value

    @property
    def click_lock(cls) -> bool:
        return cls._get_bool("click_lock", True)

    @click_lock.setter
    def click_lock(cls, value: bool) -> None:
        cls._set("click_lock", bool(value))

    @property
    def ClickLock(cls) -> bool:
        return cls.click_lock

    @ClickLock.setter
    def ClickLock(cls, value: bool) -> None:
        cls.click_lock = value

    @property
    def scale(cls) -> int:
        val = cls._get_int("scale", 100)
        return max(MIN_SCALE, min(MAX_SCALE, val))

    @scale.setter
    def scale(cls, value: int) -> None:
        clamped = max(MIN_SCALE, min(MAX_SCALE, int(value)))
        cls._set("scale", clamped)

    @property
    def Scale(cls) -> int:
        return cls.scale

    @Scale.setter
    def Scale(cls, value: int) -> None:
        cls.scale = value

    @property
    def gap(cls) -> int:
        val = cls._get_int("gap", 8)
        return max(0, min(MAX_GAP, val))

    @gap.setter
    def gap(cls, value: int) -> None:
        clamped = max(0, min(MAX_GAP, int(value)))
        cls._set("gap", clamped)

    @property
    def Gap(cls) -> int:
        return cls.gap

    @Gap.setter
    def Gap(cls, value: int) -> None:
        cls.gap = value

    @property
    def accent(cls) -> Optional[Tuple[float, float, float]]:
        raw = cls._data.get("accent")
        if raw is None:
            return None
        if isinstance(raw, (list, tuple)) and len(raw) >= 3:
            return (float(raw[0]), float(raw[1]), float(raw[2]))
        if isinstance(raw, str) and raw.startswith("#"):
            try:
                hex_str = raw.lstrip("#")
                if len(hex_str) == 6:
                    r = int(hex_str[0:2], 16) / 255.0
                    g = int(hex_str[2:4], 16) / 255.0
                    b = int(hex_str[4:6], 16) / 255.0
                    return (r, g, b)
            except Exception:
                return None
        return None

    @accent.setter
    def accent(cls, value: Optional[Tuple[float, float, float]]) -> None:
        if value is None:
            cls._set("accent", None)
        else:
            r = value[0] / 255.0 if value[0] > 1.0 else float(value[0])
            g = value[1] / 255.0 if value[1] > 1.0 else float(value[1])
            b = value[2] / 255.0 if value[2] > 1.0 else float(value[2])
            cls._set("accent", [round(r, 4), round(g, 4), round(b, 4)])

    @property
    def Accent(cls) -> Optional[Tuple[float, float, float]]:
        return cls.accent

    @Accent.setter
    def Accent(cls, value: Optional[Tuple[float, float, float]]) -> None:
        cls.accent = value

    @property
    def autostart(cls) -> bool:
        try:
            return Autostart.is_enabled()
        except Exception:
            return False

    @autostart.setter
    def autostart(cls, value: bool) -> None:
        try:
            script_dir = Path(__file__).resolve().parent
            entry_script = script_dir / "dynamic_island.py"
            exec_cmd = f"python3 {entry_script}" if entry_script.is_file() else None
            Autostart.set(bool(value), exec_cmd=exec_cmd)
        except Exception as e:
            logger.error("Failed to update autostart setting: %s", e)

    @property
    def Autostart(cls) -> bool:
        return cls.autostart

    @Autostart.setter
    def Autostart(cls, value: bool) -> None:
        cls.autostart = value

class Settings(metaclass=_SettingsMeta):

    MinScale: int = MIN_SCALE
    MaxScale: int = MAX_SCALE
    MaxGap: int = MAX_GAP

    _data: dict[str, Any] = {}
    _loaded: bool = False
    _listeners: list[Callable[[str, Any], None]] = []

    @classmethod
    def load(cls) -> None:
        try:
            if CONFIG_FILE.is_file():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cls._data = json.load(f)
            else:
                cls._data = {}
        except Exception as e:
            logger.warning("Failed loading settings from %s: %s", CONFIG_FILE, e)
            cls._data = {}
        cls._loaded = True

    @classmethod
    def save(cls) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            tmp_file = CONFIG_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(cls._data, f, indent=2)
            tmp_file.replace(CONFIG_FILE)
        except Exception as e:
            logger.error("Failed saving settings to %s: %s", CONFIG_FILE, e)

    @classmethod
    def _ensure_loaded(cls) -> None:
        if not cls._loaded:
            cls.load()

    @classmethod
    def _get_bool(cls, key: str, default: bool) -> bool:
        cls._ensure_loaded()
        val = cls._data.get(key)
        if val is None:
            return default
        return bool(val)

    @classmethod
    def _get_int(cls, key: str, default: int) -> int:
        cls._ensure_loaded()
        val = cls._data.get(key)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @classmethod
    def _set(cls, key: str, value: Any) -> None:
        cls._ensure_loaded()
        if cls._data.get(key) == value:
            return
        cls._data[key] = value
        cls.save()
        for listener in list(cls._listeners):
            try:
                listener(key, value)
            except Exception as e:
                logger.error("Error in settings change listener: %s", e)

    @classmethod
    def add_change_listener(cls, listener: Callable[[str, Any], None]) -> None:
        if listener not in cls._listeners:
            cls._listeners.append(listener)

    @classmethod
    def remove_change_listener(cls, listener: Callable[[str, Any], None]) -> None:
        if listener in cls._listeners:
            cls._listeners.remove(listener)

Settings.load()

if __name__ == "__main__":
    print("Testing Settings...")
    print(f"Lyrics: {Settings.lyrics}")
    print(f"LyricEffects: {Settings.lyric_effects}")
    print(f"Rim: {Settings.rim}")
    print(f"AppVolume: {Settings.app_volume}")
    print(f"Network: {Settings.network}")
    print(f"HideFullscreen: {Settings.hide_fullscreen}")
    print(f"Scale: {Settings.scale}")
    print(f"Gap: {Settings.gap}")
    print(f"Accent: {Settings.accent}")
    print(f"Autostart: {Settings.autostart}")
    print("All settings accessed successfully!")
