#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ctypes

try:
    ctypes.CDLL("libgtk4-layer-shell.so", ctypes.RTLD_GLOBAL)
except Exception:
    pass

import datetime
import logging
import os
import shutil
import signal
import subprocess
import sys
import traceback
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WAYLAND_DIR = SCRIPT_DIR
FONTS_DIR = SCRIPT_DIR / "fonts"

LOG_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "dynamic-island"
LOG_FILE = LOG_DIR / "island.log"

logger = logging.getLogger("dynamic_island")

def setup_logging(verbose: bool) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > 5 * 1024 * 1024:
            old_log = LOG_DIR / "island.log.old"
            try:
                shutil.move(LOG_FILE, old_log)
            except Exception:
                pass

        file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        file_handler.setLevel(logging.DEBUG)

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.addHandler(file_handler)

        if verbose:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setFormatter(
                logging.Formatter("[%(levelname)s] %(message)s")
            )
            stream_handler.setLevel(logging.DEBUG)
            root.addHandler(stream_handler)

        logger.info("=== Dynamic Island Started ===")
        logger.info("Python: %s (%s)", sys.version.split()[0], sys.executable)
        logger.info("Directory: %s", SCRIPT_DIR)
        logger.info("Wayland display: %s", os.environ.get("WAYLAND_DISPLAY", "None"))
    except Exception as exc:
        print(f"Warning: Failed to setup file logger at {LOG_FILE}: {exc}", file=sys.stderr)

def exception_handler(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical("Uncaught top-level exception:", exc_info=(exc_type, exc_value, exc_tb))
    print("\n\033[1;31m[Dynamic Island Crash]\033[0m An unexpected error occurred:", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)
    print(f"\nFull log written to: {LOG_FILE}\n", file=sys.stderr)

sys.excepthook = exception_handler

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

def check_dependencies() -> list[tuple[str, str, bool, str]]:
    results = []

    # 1. Python version
    py_ver = f"{sys.version.split()[0]} ({sys.executable})"
    results.append(("Python >= 3.9", py_ver, sys.version_info >= (3, 9), "Install Python 3.9 or newer"))

    # 2. Wayland session
    wayland_display = os.environ.get("WAYLAND_DISPLAY")
    is_wayland = bool(wayland_display or os.environ.get("XDG_SESSION_TYPE") == "wayland")
    wayland_info = wayland_display if wayland_display else ("None" if not is_wayland else "Wayland detected")
    results.append(("Wayland Session", wayland_info, is_wayland, "Log into a Wayland session (Hyprland, Sway, KDE, GNOME)"))

    # 3. Python-GObject (gi)
    try:
        import gi
        results.append(("PyGObject (gi)", "Installed", True, "sudo pacman -S python-gobject"))
    except ImportError:
        results.append(("PyGObject (gi)", "Missing", False, "Arch: sudo pacman -S python-gobject | Ubuntu: sudo apt install python3-gi"))

    # 4. GTK 4.0
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
        results.append(("GTK 4.0", "Available", True, "sudo pacman -S gtk4"))
    except Exception as exc:
        results.append(("GTK 4.0", f"Missing ({exc})", False, "Arch: sudo pacman -S gtk4 | Ubuntu: sudo apt install libgtk-4-1"))

    # 5. Gtk4LayerShell 1.0
    try:
        try:
            ctypes.CDLL("libgtk4-layer-shell.so", ctypes.RTLD_GLOBAL)
        except Exception:
            pass
        import gi
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell
        results.append(("Gtk4LayerShell 1.0", "Available", True, "sudo pacman -S gtk4-layer-shell"))
    except Exception as exc:
        results.append(("Gtk4LayerShell 1.0", f"Missing ({exc})", False, "Arch: sudo pacman -S gtk4-layer-shell | Fedora: sudo dnf install gtk4-layer-shell | Ubuntu: sudo apt install libgtk4-layer-shell0"))

    # 6. Cairo (pycairo)
    try:
        import cairo
        results.append(("Cairo (pycairo)", "Installed", True, "sudo pacman -S python-cairo"))
    except ImportError:
        results.append(("Cairo (pycairo)", "Missing", False, "Arch: sudo pacman -S python-cairo | Ubuntu: sudo apt install python3-cairo"))

    # 7. Requests
    try:
        import requests
        results.append(("Requests", requests.__version__, True, "sudo pacman -S python-requests"))
    except ImportError:
        results.append(("Requests", "Missing", False, "Arch: sudo pacman -S python-requests | Ubuntu: sudo apt install python3-requests"))

    # 8. Pillow (PIL)
    try:
        import PIL
        results.append(("Pillow (PIL)", PIL.__version__, True, "sudo pacman -S python-pillow"))
    except ImportError:
        results.append(("Pillow (PIL)", "Optional (generic shelf icons will be used)", True, "Arch: sudo pacman -S python-pillow"))

    # 9. Roc compiler
    roc_bin = find_roc_binary()
    results.append(("Roc Compiler", str(roc_bin) if roc_bin else "Optional", True, "https://www.roc-lang.org/"))

    return results

def run_doctor() -> int:
    print("==================================================================")
    print("           Dynamic Island (Roc) - System Doctor")
    print("==================================================================")
    checks = check_dependencies()
    failures = 0
    for name, info, ok, hint in checks:
        if ok:
            print(f"  \033[1;32m[OK]\033[0m   {name:<22} : {info}")
        else:
            failures += 1
            print(f"  \033[1;31m[FAIL]\033[0m {name:<22} : {info}")
            print(f"         \033[1;33mFix:\033[0m {hint}")
    print("==================================================================")
    print(f"Diagnostic log file: {LOG_FILE}")
    if failures > 0:
        print(f"\033[1;31mFound {failures} issue(s) that prevent Dynamic Island from starting.\033[0m")
        return 1
    print("\033[1;32mAll required dependencies are satisfied! Dynamic Island can start.\033[0m")
    return 0

def show_log() -> int:
    if not LOG_FILE.exists():
        print(f"No log file found at: {LOG_FILE}")
        return 0
    print(f"=== Last entries from {LOG_FILE} ===")
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            for line in lines[-100:]:
                print(line, end="")
    except Exception as exc:
        print(f"Error reading log: {exc}", file=sys.stderr)
        return 1
    return 0

def redirect_output_to_log(verbose: bool) -> None:
    if verbose:
        return
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_fd = os.open(LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
    except Exception as exc:
        logger.warning("Could not redirect stdio to log: %s", exc)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dynamic Island for Arch Linux Wayland (Roc Port)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--view",
        type=str,
        default=None,
        help="Force island view: Idle, Media, Timer, Volume, Charge, Focus, Toast, Notice, MediaBig, IdleBig, TimerBig, TimerSet, Menu, Settings, Look, Shelf, Update",
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
        "--doctor",
        action="store_true",
        help="Check system dependencies and print diagnostic report",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Display the contents of the latest island log file",
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

    if args.doctor:
        return run_doctor()

    if args.log:
        return show_log()

    setup_logging(args.verbose)
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

    # Verify critical dependencies before suppressing terminal output
    checks = check_dependencies()
    critical_fails = [c for c in checks if not c[2]]
    if critical_fails:
        logger.error("Startup aborted due to missing dependencies:")
        print("\n\033[1;31m[Dynamic Island Startup Error]\033[0m Missing dependencies:", file=sys.stderr)
        for name, info, _, hint in critical_fails:
            logger.error("  - %s: %s (Fix: %s)", name, info, hint)
            print(f"  • \033[1;33m{name}\033[0m: {info}", file=sys.stderr)
            print(f"    Fix: {hint}", file=sys.stderr)
        print(f"\nFor full system diagnostics run: dynamic-island --doctor", file=sys.stderr)
        print(f"Log written to: {LOG_FILE}\n", file=sys.stderr)
        return 1

    redirect_output_to_log(args.verbose)

    os.environ.setdefault("GSK_RENDERER", "gl")
    os.environ.setdefault("GTK_A11Y", "none")

    try:
        ctypes.CDLL("libgtk4-layer-shell.so", ctypes.RTLD_GLOBAL)
    except Exception as exc:
        logger.debug("ctypes load libgtk4-layer-shell: %s", exc)

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
        try:
            if main_win is None:
                main_win = MainWindow(
                    application,
                    forced_view=args.view,
                    forced_timer=args.timer,
                )
            main_win.present()
            logger.info("Dynamic Island window presented successfully")
        except Exception as exc:
            logger.critical("Failed to create MainWindow:", exc_info=True)
            print(f"\n[Dynamic Island] Error presenting window: {exc}", file=sys.stderr)
            application.quit()

    app.connect("activate", on_activate)
    ret = app.run([])
    logger.info("Dynamic Island exited with code %d", ret)
    return ret

if __name__ == "__main__":
    sys.exit(main())
