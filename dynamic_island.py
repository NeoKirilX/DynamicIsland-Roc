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

def ensure_environment_silent() -> None:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    required_fonts = [
        "SF-Pro-Display-Semibold.otf",
        "SF-Pro-Text-Regular.otf",
        "SF-Pro-Text-Medium.otf",
        "SF-Pro-Text-Semibold.otf",
    ]
    source_fonts = Path("/home/neokirilx/DynamicIsland/Fonts")
    for f in required_fonts:
        target = FONTS_DIR / f
        if not target.is_file():
            source = source_fonts / f
            if source.is_file():
                try:
                    shutil.copy2(source, target)
                except Exception:
                    pass

    roc_bin = shutil.which("roc") or (Path.home() / ".local" / "bin" / "roc")
    if not (roc_bin and Path(str(roc_bin)).is_file()):
        prebuilt = Path("/home/neokirilx/roc/roc")
        if prebuilt.is_file():
            try:
                symlink = Path.home() / ".local" / "bin" / "roc"
                symlink.parent.mkdir(parents=True, exist_ok=True)
                if not symlink.exists():
                    symlink.symlink_to(prebuilt)
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
        application_id="com.github.neokirilx.dynamic_island_roc",
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
