#!/usr/bin/env python3

from __future__ import annotations

import datetime
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from settings import (
    CONFIG_DIR,
    MAX_GAP,
    MAX_HEIGHT,
    MAX_RADIUS,
    MAX_SCALE,
    MAX_TEXT,
    MIN_GLASS,
    MIN_HEIGHT,
    MIN_RADIUS,
    MIN_SCALE,
    MIN_TEXT,
    Settings,
)

logger = logging.getLogger(__name__)

EXPORTS_DIR = CONFIG_DIR / "configs"
DNI_MAGIC = "DYNAMIC_ISLAND_CONFIG"
DNI_VERSION = 1


def get_current_screen_resolution() -> tuple[int, int]:
    try:
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        display = Gdk.Display.get_default()
        if display:
            monitors = display.get_monitors()
            if monitors and monitors.get_n_items() > 0:
                geom = monitors.get_item(0).get_geometry()
                if geom.width > 0 and geom.height > 0:
                    return int(geom.width), int(geom.height)
    except Exception as e:
        logger.debug("Failed getting screen resolution via Gdk: %s", e)

    # Fallback to standard 1080p
    return 1920, 1080


class ConfigService:

    @classmethod
    def get_exportable_keys(cls) -> list[str]:
        return [
            # Appearance
            "scale",
            "gap",
            "radius",
            "glass",
            "height",
            "text_scale",
            "material",
            "align",
            "rim",
            "accent",
            # Lyrics & Anim
            "lyrics",
            "lyric_effects",
            "lyric_anim",
            "lyric_anim_style",
            "lyric_anim_speed",
            "lyric_anim_height",
            "lyric_anim_stagger",
            "lyric_lead_ahead",
            # Combo
            "combo_enabled",
            "combo_min_repeats",
            "combo_counter_style",
            "combo_split_mode",
            "combo_ignore_adlibs",
            "combo_strip_brackets",
            "combo_min_word_len",
            # Features
            "privacy_indicators",
            "weather",
            "system_stats",
            "hide_fullscreen",
            "click_lock",
            "app_volume",
            "network",
            "capitalize_title",
            "line_bar",
            "equalizer_dots",
            "language",
        ]

    @classmethod
    def export_config(
        cls,
        dest_path: Optional[str] = None,
        name: str = "Мой остров",
    ) -> tuple[bool, str]:
        try:
            EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            screen_w, screen_h = get_current_screen_resolution()

            settings_snapshot: dict[str, Any] = {}
            for key in cls.get_exportable_keys():
                val = getattr(Settings, key, None)
                if val is not None:
                    settings_snapshot[key] = val

            data = {
                "magic": DNI_MAGIC,
                "version": DNI_VERSION,
                "app_version": "1.0.6",
                "timestamp": int(time.time()),
                "exported_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": name,
                "screen": {
                    "width": screen_w,
                    "height": screen_h,
                },
                "settings": settings_snapshot,
            }

            if not dest_path:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_path = str(EXPORTS_DIR / f"island_setup_{ts}.dni")

            p = Path(dest_path)
            if not p.suffix:
                p = p.with_suffix(".dni")

            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info("Exported configuration to %s", p)
            return True, str(p)
        except Exception as exc:
            logger.error("Failed exporting config: %s", exc)
            return False, str(exc)

    @classmethod
    def import_config(
        cls,
        file_path: str,
        adapt_screen: bool = True,
    ) -> tuple[bool, str]:
        try:
            p = Path(os.path.expanduser(file_path))
            if not p.is_file():
                return False, "Файл конфигурации не найден"

            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or data.get("magic") != DNI_MAGIC:
                return False, "Неверный формат файла .dni"

            saved_settings = data.get("settings", {})
            if not isinstance(saved_settings, dict):
                return False, "В файле отсутствуют параметры настроек"

            src_screen = data.get("screen", {})
            src_w = float(src_screen.get("width", 0))
            src_h = float(src_screen.get("height", 0))

            cur_w, cur_h = get_current_screen_resolution()

            scale_multiplier = 1.0
            gap_multiplier = 1.0
            height_multiplier = 1.0

            if adapt_screen and src_w > 100 and src_h > 100:
                ratio_w = float(cur_w) / src_w
                ratio_h = float(cur_h) / src_h
                # Dampened scaling so island stays in usable ranges
                scale_multiplier = (ratio_w + ratio_h) / 2.0
                gap_multiplier = ratio_h
                height_multiplier = ratio_h

            for key, val in saved_settings.items():
                if not hasattr(Settings, key):
                    continue

                adapted_val = val
                if adapt_screen and abs(scale_multiplier - 1.0) > 0.05:
                    if key == "scale" and isinstance(val, (int, float)):
                        # Scale visually proportionally
                        adapted_val = int(round(clamp(val * scale_multiplier, MIN_SCALE, MAX_SCALE)))
                    elif key == "gap" and isinstance(val, (int, float)):
                        adapted_val = int(round(clamp(val * gap_multiplier, 0, MAX_GAP)))
                    elif key == "height" and isinstance(val, (int, float)):
                        adapted_val = int(round(clamp(val * height_multiplier, 0, MAX_HEIGHT)))

                try:
                    setattr(Settings, key, adapted_val)
                except Exception as e:
                    logger.debug("Could not set imported key %s: %s", key, e)

            # Persist changes
            Settings.save(debounce=False)
            conf_name = data.get("name") or p.stem
            return True, f"Конфиг '{conf_name}' успешно применён"
        except Exception as exc:
            logger.error("Failed importing config: %s", exc)
            return False, f"Ошибка импорта: {exc}"


def clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))
