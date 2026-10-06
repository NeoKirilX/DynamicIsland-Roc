#!/usr/bin/env python3

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

try:
    from icon import Glyph
except ImportError:
    from .icon import Glyph

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "dynamic-island"
WEATHER_CACHE_FILE = CACHE_DIR / "weather.json"
CACHE_TTL: float = 1200.0  # 20 minutes

WMO_CONDITIONS: dict[int, tuple[str, str]] = {
    0: ("Ясно", "sun"),
    1: ("Ясно", "sun"),
    2: ("Облачно", "cloud"),
    3: ("Пасмурно", "cloud"),
    45: ("Туман", "cloud"),
    48: ("Иней", "cloud"),
    51: ("Морось", "rain"),
    53: ("Морось", "rain"),
    55: ("Морось", "rain"),
    56: ("Морось", "rain"),
    57: ("Морось", "rain"),
    61: ("Дождь", "rain"),
    63: ("Дождь", "rain"),
    65: ("Сильный дождь", "rain"),
    66: ("Дождь", "rain"),
    67: ("Сильный дождь", "rain"),
    71: ("Снег", "snow"),
    73: ("Снег", "snow"),
    75: ("Сильный снег", "snow"),
    77: ("Снежная крупа", "snow"),
    80: ("Ливень", "rain"),
    81: ("Ливень", "rain"),
    82: ("Ливень", "rain"),
    85: ("Снегопад", "snow"),
    86: ("Снегопад", "snow"),
    95: ("Гроза", "bolt"),
    96: ("Гроза", "bolt"),
    99: ("Гроза", "bolt"),
}

def format_temperature(temp: float) -> str:
    rounded = int(round(temp))
    if rounded > 0:
        return f"+{rounded}°"
    return f"{rounded}°"

@dataclass(frozen=True)
class WeatherInfo:
    temperature: float
    apparent_temperature: float
    weather_code: int
    is_day: bool
    condition: str
    icon_glyph: Glyph
    temp_str: str
    city: str = ""
    fetched_at: float = 0.0

    @classmethod
    def from_raw(
        cls,
        temp: float,
        app_temp: float,
        code: int,
        is_day: bool,
        city: str = "",
        fetched_at: float = 0.0,
    ) -> WeatherInfo:
        cond_text, icon_type = WMO_CONDITIONS.get(code, ("Ясно", "sun"))
        if icon_type == "sun":
            glyph = Glyph.Sun if is_day else Glyph.Moon
        elif icon_type == "cloud":
            glyph = Glyph.Cloud
        elif icon_type == "rain":
            glyph = Glyph.CloudRain
        elif icon_type == "snow":
            glyph = Glyph.CloudSnow
        elif icon_type == "bolt":
            glyph = Glyph.Bolt
        else:
            glyph = Glyph.Sun if is_day else Glyph.Moon

        return cls(
            temperature=temp,
            apparent_temperature=app_temp,
            weather_code=code,
            is_day=is_day,
            condition=cond_text,
            icon_glyph=glyph,
            temp_str=format_temperature(temp),
            city=city,
            fetched_at=fetched_at or time.time(),
        )


class WeatherService:

    def __init__(
        self,
        on_changed: Optional[Callable[[WeatherInfo], None]] = None,
        auto_start: bool = True,
    ) -> None:
        self._lock = threading.RLock()
        self._on_changed = on_changed
        self._current_weather: Optional[WeatherInfo] = None
        self._simulated: Optional[WeatherInfo] = None

        self._lat: Optional[float] = None
        self._lon: Optional[float] = None
        self._city: str = ""

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._load_cache()

        if auto_start:
            self.start()

    @property
    def current(self) -> Optional[WeatherInfo]:
        with self._lock:
            if self._simulated is not None:
                return self._simulated
            return self._current_weather

    @property
    def has_weather(self) -> bool:
        return self.current is not None

    def simulate(
        self,
        temp: Optional[float] = None,
        code: int = 0,
        is_day: bool = True,
        city: str = "Москва",
    ) -> None:
        with self._lock:
            if temp is None:
                self._simulated = None
                curr = self._current_weather
            else:
                self._simulated = WeatherInfo.from_raw(
                    temp=temp,
                    app_temp=temp,
                    code=code,
                    is_day=is_day,
                    city=city,
                    fetched_at=time.time(),
                )
                curr = self._simulated

        if self._on_changed and curr:
            try:
                self._on_changed(curr)
            except Exception as e:
                logger.error("Error in WeatherService simulation callback: %s", e)

    def _load_cache(self) -> None:
        try:
            if not WEATHER_CACHE_FILE.is_file():
                return
            with open(WEATHER_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._lat = data.get("latitude")
            self._lon = data.get("longitude")
            self._city = data.get("city", "")

            cached_at = float(data.get("fetched_at", 0))
            if time.time() - cached_at < CACHE_TTL * 2:
                self._current_weather = WeatherInfo.from_raw(
                    temp=float(data["temperature"]),
                    app_temp=float(data.get("apparent_temperature", data["temperature"])),
                    code=int(data.get("weather_code", 0)),
                    is_day=bool(data.get("is_day", True)),
                    city=self._city,
                    fetched_at=cached_at,
                )
        except Exception as e:
            logger.debug("Could not read weather cache: %s", e)

    def _save_cache(self, info: WeatherInfo) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "latitude": self._lat,
                "longitude": self._lon,
                "city": self._city,
                "temperature": info.temperature,
                "apparent_temperature": info.apparent_temperature,
                "weather_code": info.weather_code,
                "is_day": info.is_day,
                "fetched_at": info.fetched_at,
            }
            tmp = WEATHER_CACHE_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            tmp.replace(WEATHER_CACHE_FILE)
        except Exception as e:
            logger.debug("Could not save weather cache: %s", e)

    def _resolve_location(self) -> bool:
        if self._lat is not None and self._lon is not None:
            return True

        # Try auto-detecting via free IP geolocator
        endpoints = [
            ("https://ipapi.co/json/", lambda d: (float(d["latitude"]), float(d["longitude"]), d.get("city", ""))),
            ("http://ip-api.com/json/", lambda d: (float(d["lat"]), float(d["lon"]), d.get("city", ""))),
        ]

        for url, parser in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "DynamicIsland/1.0"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    raw = json.loads(resp.read().decode())
                    lat, lon, city = parser(raw)
                    self._lat = lat
                    self._lon = lon
                    self._city = city
                    return True
            except Exception as e:
                logger.debug("Failed geolocating with %s: %s", url, e)

        # Fallback to Moscow coordinates if offline or failed
        self._lat = 55.7558
        self._lon = 37.6173
        self._city = "Москва"
        return True

    def fetch_weather_now(self) -> Optional[WeatherInfo]:
        if not self._resolve_location():
            return None

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={self._lat:.4f}&longitude={self._lon:.4f}&"
            f"current=temperature_2m,apparent_temperature,is_day,weather_code"
        )

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DynamicIsland/1.0"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode())

            current_data = data.get("current", {})
            temp = float(current_data.get("temperature_2m", 0.0))
            app_temp = float(current_data.get("apparent_temperature", temp))
            code = int(current_data.get("weather_code", 0))
            is_day = bool(current_data.get("is_day", 1))

            weather = WeatherInfo.from_raw(
                temp=temp,
                app_temp=app_temp,
                code=code,
                is_day=is_day,
                city=self._city,
                fetched_at=time.time(),
            )

            with self._lock:
                self._current_weather = weather
            self._save_cache(weather)

            if self._on_changed:
                try:
                    self._on_changed(weather)
                except Exception as e:
                    logger.error("Error in on_changed weather callback: %s", e)

            return weather
        except Exception as e:
            logger.debug("Error fetching Open-Meteo weather: %s", e)
            return self._current_weather

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="WeatherServiceWorker",
        )
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _worker(self) -> None:
        while self._running:
            try:
                now = time.time()
                cached_time = self._current_weather.fetched_at if self._current_weather else 0.0
                if now - cached_time >= CACHE_TTL:
                    self.fetch_weather_now()
            except Exception as e:
                logger.debug("Error in WeatherService loop: %s", e)

            # Sleep in small increments for quick exit
            for _ in range(int(CACHE_TTL)):
                if not self._running:
                    break
                time.sleep(1.0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing WeatherService...")
    ws = WeatherService(auto_start=False)
    print("Cached weather:", ws.current)
    info = ws.fetch_weather_now()
    print("Fetched weather:", info)
    ws.simulate(temp=21.5, code=0, is_day=True, city="Санкт-Петербург")
    print("Simulated weather:", ws.current)
    ws.simulate()
    print("Reset weather:", ws.current)
    print("WeatherService tests passed!")
