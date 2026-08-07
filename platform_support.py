"""Single source of truth for OS-specific behaviour.

Everything the rest of the app needs that differs between macOS and Windows
lives here, so `gui.py`, `downloader.py` and `config.py` stay portable.
"""

import os
import signal
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

# macOS Tk ships its own cursor names; every other platform uses the X11 set.
if IS_MACOS:
    CURSOR_CLICKABLE = "pointinghand"
    CURSOR_DISABLED = "notallowed"
else:
    CURSOR_CLICKABLE = "hand2"
    CURSOR_DISABLED = "no"

CURSOR_DEFAULT = ""

EXECUTABLE_SUFFIX = ".exe" if IS_WINDOWS else ""

# Where a user's own yt-dlp/ffmpeg install typically lives when we are not frozen.
if IS_MACOS:
    SYSTEM_TOOL_PATHS = ["/usr/local/bin", "/opt/homebrew/bin"]
else:
    SYSTEM_TOOL_PATHS = []

# Sized so the content still fits with MAX_VISIBLE_ROWS url rows showing, plus
# the notebook tab strip and the two-dropdown options row. Windows needs more
# room, where native ttk widgets and the default font render taller than Aqua.
WINDOW_GEOMETRY = "660x830" if IS_WINDOWS else "600x760"


def bundled_tools_bin_dir():
    """Directory holding the vendored yt-dlp/ffmpeg/deno, or None when not frozen.

    PyInstaller exposes the folder it unpacked `datas` into as `sys._MEIPASS`
    on both platforms: `<app>.app/Contents/Frameworks` on macOS and
    `<dist>/yt-dlp-gui/_internal` on Windows.
    """
    if not getattr(sys, "frozen", False):
        return None

    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "tools", "bin"))

    exe_dir = os.path.dirname(sys.executable)
    if IS_MACOS:
        candidates.append(os.path.normpath(os.path.join(exe_dir, "..", "Frameworks", "tools", "bin")))
    else:
        candidates.append(os.path.join(exe_dir, "_internal", "tools", "bin"))
        candidates.append(os.path.join(exe_dir, "tools", "bin"))

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return None


def subprocess_flags():
    """Popen/run kwargs that keep child processes headless and killable as a group."""
    if IS_WINDOWS:
        # CREATE_NO_WINDOW stops a console flashing up for every yt-dlp call;
        # CREATE_NEW_PROCESS_GROUP makes the whole tree addressable on cancel.
        return {
            "creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        }
    return {"start_new_session": True}


def terminate_process_tree(proc):
    """Stop a download along with any child processes it spawned (ffmpeg, etc.)."""
    if IS_WINDOWS:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **subprocess_flags(),
            )
        except OSError:
            pass
        return

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        pass


# The single canonical name for this app: window title base, notification
# titles, the /ping identity string, the settings folder, all derive from this.
APP_NAME = "yt-dlp-gui"


def settings_path():
    """Per-user settings file, in the location each OS expects.

    Deliberately outside the application: writing next to the executable would
    break the macOS bundle signature and needs admin rights under Program Files.
    """
    home = os.path.expanduser("~")
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    else:
        base = os.path.join(home, "Library", "Application Support")
    return os.path.join(base, APP_NAME, "settings.json")


def browser_profile_dirs():
    """Where each browser keeps the profile yt-dlp reads cookies out of.

    Checking the profile rather than the application matters: a browser that is
    installed but has never been run has no cookie database to read.
    """
    home = os.path.expanduser("~")
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        roaming = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return {
            "chrome": [os.path.join(local, "Google", "Chrome", "User Data")],
            "firefox": [os.path.join(roaming, "Mozilla", "Firefox")],
            "opera": [os.path.join(roaming, "Opera Software", "Opera Stable")],
        }

    support = os.path.join(home, "Library", "Application Support")
    return {
        "chrome": [os.path.join(support, "Google", "Chrome")],
        "firefox": [os.path.join(support, "Firefox")],
        "opera": [os.path.join(support, "com.operasoftware.Opera")],
    }


def installed_browsers(candidates):
    """Subset of `candidates` that actually has a profile on this machine."""
    profile_dirs = browser_profile_dirs()
    return [
        browser
        for browser in candidates
        if any(os.path.isdir(path) for path in profile_dirs.get(browser, []))
    ]


def normalize_wheel_delta(event):
    """Scroll units for one mouse-wheel event.

    Windows reports multiples of 120 per notch; macOS reports small integers.
    """
    if IS_WINDOWS:
        return int(-1 * (event.delta / 120))
    return int(-1 * event.delta)
