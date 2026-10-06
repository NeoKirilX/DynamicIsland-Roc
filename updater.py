#!/usr/bin/env python3

from __future__ import annotations

import logging
import os
import shutil
import sys
import tarfile
import tempfile
import threading
import time
from typing import Callable, Optional
import requests

logger = logging.getLogger(__name__)

REPO_OWNER = "NeoKirilX"
REPO_NAME = "DynamicIsland-Roc"
CURRENT_VERSION = "1.0.6"
API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

class UpdateState:
    IDLE = "idle"
    CHECKING = "checking"
    LATEST = "latest"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    FAILED = "failed"
    READY = "ready"

class Updater:
    _instance: Optional[Updater] = None

    @classmethod
    def get(cls) -> Updater:
        if cls._instance is None:
            cls._instance = Updater()
        return cls._instance

    def __init__(self) -> None:
        self.current_version: str = CURRENT_VERSION
        self.latest_version: str = CURRENT_VERSION
        self.state: str = UpdateState.IDLE
        self.notes: list[str] = []
        self.changelog: str = ""
        self.download_url: str = ""
        self.percent: float = 0.0
        self.error_message: str = ""
        self._callbacks: list[Callable[[], None]] = []
        self._lock = threading.Lock()
        self._last_checked: float = 0.0

    def add_callback(self, cb: Callable[[], None]) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def _notify(self) -> None:
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def check_async(self, force: bool = False) -> None:
        if self.state in (UpdateState.CHECKING, UpdateState.DOWNLOADING):
            return
        now = time.monotonic()
        if not force and now - self._last_checked < 1800.0 and self.state != UpdateState.FAILED:
            return

        self._last_checked = now
        self.state = UpdateState.CHECKING
        self._notify()

        thread = threading.Thread(target=self._check_worker, daemon=True)
        thread.start()

    def _check_worker(self) -> None:
        try:
            resp = requests.get(API_URL, headers={"User-Agent": "DynamicIsland/1.0"}, timeout=12.0)
            if resp.status_code == 200:
                data = resp.json()
                tag = data.get("tag_name", "").lstrip("v")
                body = data.get("body", "")

                notes = []
                for line in body.splitlines():
                    line_s = line.strip()
                    if line_s.startswith("- "):
                        notes.append(line_s[2:].strip())
                    elif line_s.startswith("* "):
                        notes.append(line_s[2:].strip())

                download_url = ""
                for asset in data.get("assets", []):
                    name = asset.get("name", "")
                    if name.endswith(".tar.gz") or name == "dynamic-island":
                        download_url = asset.get("browser_download_url", "")
                        break

                with self._lock:
                    self.latest_version = tag or self.current_version
                    self.changelog = body
                    self.notes = notes
                    self.download_url = download_url
                    if self._is_newer(self.latest_version, self.current_version):
                        self.state = UpdateState.AVAILABLE
                    else:
                        self.state = UpdateState.LATEST
            else:
                with self._lock:
                    self.state = UpdateState.FAILED
                    self.error_message = f"HTTP {resp.status_code}"
        except Exception as exc:
            logger.debug("Update check failed: %s", exc)
            with self._lock:
                self.state = UpdateState.FAILED
                self.error_message = str(exc)
        self._notify()

    def start_download_async(self) -> None:
        if self.state == UpdateState.DOWNLOADING or not self.download_url:
            return
        self.state = UpdateState.DOWNLOADING
        self.percent = 0.0
        self._notify()

        thread = threading.Thread(target=self._download_worker, daemon=True)
        thread.start()

    def _download_worker(self) -> None:
        try:
            resp = requests.get(self.download_url, headers={"User-Agent": "DynamicIsland/1.0"}, stream=True, timeout=60.0)
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp_file:
                tmp_path = tmp_file.name
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        tmp_file.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            with self._lock:
                                self.percent = min(1.0, downloaded / float(total))
                            self._notify()

            with self._lock:
                self.percent = 1.0
                self.state = UpdateState.READY
            self._notify()

            # Install new binary
            self._install_binary(tmp_path)
        except Exception as exc:
            logger.error("Download failed: %s", exc)
            with self._lock:
                self.state = UpdateState.FAILED
                self.error_message = str(exc)
            self._notify()

    def _install_binary(self, downloaded_path: str) -> None:
        try:
            exe_path = os.path.realpath(sys.argv[0])
            dest_dir = os.path.dirname(exe_path)

            if downloaded_path.endswith(".tar.gz") or tarfile.is_tarfile(downloaded_path):
                with tarfile.open(downloaded_path, "r:*") as tar:
                    tar.extractall(path=dest_dir)
            else:
                # Standalone binary
                target = os.path.join(dest_dir, "dynamic-island")
                shutil.move(downloaded_path, target)
                os.chmod(target, 0o755)
        except Exception as exc:
            logger.error("Installation failed: %s", exc)

    def restart(self) -> None:
        try:
            exe_path = os.path.realpath(sys.argv[0])
            os.execv(exe_path, [exe_path])
        except Exception as exc:
            logger.error("Restart failed: %s", exc)

    @staticmethod
    def _is_newer(latest: str, current: str) -> bool:
        def parse_v(v: str) -> list[int]:
            parts = []
            for p in v.split("."):
                try:
                    parts.append(int(p))
                except ValueError:
                    break
            return parts or [0]
        return parse_v(latest) > parse_v(current)
