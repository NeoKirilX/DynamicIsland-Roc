#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import signal
import subprocess
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WAYLAND_DIR = SCRIPT_DIR
FONTS_DIR = SCRIPT_DIR / "fonts"

def find_roc_binary() -> Path | None:
    which_roc = shutil.which("roc")
    if which_roc:
        p = Path(which_roc)
        if p.is_file() and os.access(p, os.X_OK):
            return p

    home = Path.home()
    candidates = [
        home / ".local" / "bin" / "roc",
        home / "roc" / "roc",
    ]
    for cand in candidates:
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None

def ensure_environment_silent() -> None:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    required_fonts = [
        "SF-Pro-Display-Semibold.otf",
        "SF-Pro-Text-Regular.otf",
        "SF-Pro-Text-Medium.otf",
        "SF-Pro-Text-Semibold.otf",
    ]
    xdg_data = os.environ.get("XDG_DATA_HOME")
    data_home = Path(xdg_data) if xdg_data else (Path.home() / ".local" / "share")
    font_sources = [
        Path.home() / "DynamicIsland" / "Fonts",
        data_home / "fonts",
        Path.home() / ".fonts",
    ]
    for f in required_fonts:
        target = FONTS_DIR / f
        if not target.is_file():
            for s_dir in font_sources:
                source = s_dir / f
                if source.is_file():
                    try:
                        shutil.copy2(source, target)
                        break
                    except Exception:
                        pass

    roc_bin = find_roc_binary()
    home = Path.home()
    prebuilt = home / "roc" / "roc"
    local_roc = home / ".local" / "bin" / "roc"
    if (not roc_bin or not local_roc.exists()) and prebuilt.is_file():
        try:
            local_roc.parent.mkdir(parents=True, exist_ok=True)
            if not local_roc.exists():
                local_roc.symlink_to(prebuilt)
        except Exception:
            pass

    island_symlink = home / ".local" / "bin" / "dynamic-island"
    if not island_symlink.exists():
        try:
            island_symlink.parent.mkdir(parents=True, exist_ok=True)
            island_symlink.symlink_to(SCRIPT_DIR / "dynamic_island.py")
        except Exception:
            pass

def silence_output_unless_verbose(verbose: bool) -> None:
    if verbose:
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        os.close(devnull)
    except Exception:
        pass

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dynamic Island for Arch Linux Wayland (Roc Port)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--view",
        type=str,
        default=None,
        help="Force island view: Idle, Media, Timer, Volume, Charge, Toast, Notice, MediaBig, IdleBig, TimerBig, TimerSet, Menu, Settings, Look",
    )
    parser.add_argument(
        "--timer",
        type=float,
        default=0.0,
        help="Start with an active timer countdown of N seconds (e.g. --timer 90)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print diagnostic output to terminal instead of running silently",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run Roc test suite before launching",
    )
    parser.add_argument(
        "--roc-check",
        action="store_true",
        help="Verify all Roc modules compile and pass unit tests, then exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="DynamicIsland-Roc 1.0.0",
    )

    args = parser.parse_args()

    ensure_environment_silent()

    if args.roc_check:
        test_script = SCRIPT_DIR / "test_all.sh"
        if test_script.is_file():
            return subprocess.run([str(test_script)]).returncode
        return 1

    if args.test:
        test_script = SCRIPT_DIR / "test_all.sh"
        if test_script.is_file():
            code = subprocess.run([str(test_script)]).returncode
            if code != 0:
                return code

    silence_output_unless_verbose(args.verbose)

    os.environ.setdefault("GSK_RENDERER", "gl")
    os.environ.setdefault("GTK_A11Y", "none")

    try:
        ctypes.CDLL("libgtk4-layer-shell.so", ctypes.RTLD_GLOBAL)
    except Exception:
        pass

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gio, GLib, Gtk

    for p in (SCRIPT_DIR, WAYLAND_DIR):
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

    from main_window import MainWindow

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = Gtk.Application(
        application_id="io.github.dynamic_island",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    main_win: MainWindow | None = None

    def on_activate(application: Gtk.Application) -> None:
        nonlocal main_win
        if main_win is None:
            main_win = MainWindow(
                application,
                forced_view=args.view,
                forced_timer=args.timer,
            )
        main_win.present()

    app.connect("activate", on_activate)
    return app.run([])

if __name__ == "__main__":
    sys.exit(main())
