"""Exercise the Windows branches of platform_support/config/notifier from macOS.

We can't run the app on Windows here, so we fake sys.platform (plus the
Windows-only subprocess constants) and re-import the modules.
"""
import base64
import importlib
import os
import subprocess
import sys
import tempfile

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

# Windows-only constants that platform_support references on the win32 branch.
subprocess.CREATE_NO_WINDOW = 0x08000000
subprocess.CREATE_NEW_PROCESS_GROUP = 0x00000200

real_platform = sys.platform


def reload_as(platform_name, frozen=False, meipass=None):
    sys.platform = platform_name
    if frozen:
        sys.frozen = True
        if meipass:
            sys._MEIPASS = meipass
    else:
        for attr in ("frozen", "_MEIPASS"):
            if hasattr(sys, attr):
                delattr(sys, attr)
    for mod in ("platform_support", "config", "notifier"):
        sys.modules.pop(mod, None)
    ps = importlib.import_module("platform_support")
    cfg = importlib.import_module("config")
    nt = importlib.import_module("notifier")
    return ps, cfg, nt


try:
    # --- Windows, not frozen -------------------------------------------------
    ps, cfg, nt = reload_as("win32")
    assert ps.IS_WINDOWS and not ps.IS_MACOS
    assert ps.CURSOR_CLICKABLE == "hand2", ps.CURSOR_CLICKABLE
    assert ps.CURSOR_DISABLED == "no", ps.CURSOR_DISABLED
    assert ps.EXECUTABLE_SUFFIX == ".exe"
    assert cfg.YT_DLP_BIN == "yt-dlp.exe", cfg.YT_DLP_BIN
    assert cfg.EXTRA_PATHS == [], cfg.EXTRA_PATHS
    assert cfg.WINDOW_GEOMETRY == "660x830", cfg.WINDOW_GEOMETRY
    print("TEST 1 PASSED: Windows cursors, .exe suffix, PATH fallback, geometry")

    # Popen kwargs must be the Windows flags, never the POSIX session switch.
    flags = ps.subprocess_flags()
    assert "creationflags" in flags and "start_new_session" not in flags, flags
    assert flags["creationflags"] == (0x08000000 | 0x00000200), flags
    print("TEST 2 PASSED: Windows spawn flags (no-window + new process group)")

    # --- Windows, frozen: tools resolve out of _internal ---------------------
    with tempfile.TemporaryDirectory() as tmp:
        meipass = os.path.join(tmp, "_internal")
        os.makedirs(os.path.join(meipass, "tools", "bin"))
        open(os.path.join(meipass, "tools", "bin", "yt-dlp.exe"), "w").close()

        ps, cfg, nt = reload_as("win32", frozen=True, meipass=meipass)
        expected = os.path.join(meipass, "tools", "bin")
        assert ps.bundled_tools_bin_dir() == expected, ps.bundled_tools_bin_dir()
        assert cfg.YT_DLP_BIN == os.path.join(expected, "yt-dlp.exe"), cfg.YT_DLP_BIN
        assert cfg.EXTRA_PATHS == [expected], cfg.EXTRA_PATHS
        print("TEST 3 PASSED: frozen Windows app resolves bundled tools via _MEIPASS")

    # --- Notification escaping ----------------------------------------------
    ps, cfg, nt = reload_as("win32")
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return None

    nt.subprocess.Popen = fake_popen
    # "Path doesn't exist" is a real app message and contains an apostrophe,
    # which must be doubled to stay a valid PowerShell single-quoted string.
    nt.notify("yt-dlp-gui", "Path doesn't exist")

    assert captured["cmd"][0] == "powershell", captured["cmd"]
    assert "-EncodedCommand" in captured["cmd"]
    decoded = base64.b64decode(captured["cmd"][-1]).decode("utf-16-le")
    assert "'Path doesn''t exist'" in decoded, decoded
    assert "ShowBalloonTip(3000" in decoded, decoded
    assert "creationflags" in captured["kwargs"], captured["kwargs"]
    print("TEST 4 PASSED: Windows toast escapes quotes and runs headless")

    # A notification blowing up must never propagate into the GUI.
    def raising_popen(*a, **k):
        raise OSError("powershell missing")

    nt.subprocess.Popen = raising_popen
    nt.notify("yt-dlp-gui", "anything")
    print("TEST 5 PASSED: notification failure is swallowed, app survives")

    # --- macOS must be unchanged --------------------------------------------
    ps, cfg, nt = reload_as("darwin")
    assert ps.CURSOR_CLICKABLE == "pointinghand"
    assert ps.CURSOR_DISABLED == "notallowed"
    assert cfg.YT_DLP_BIN == "yt-dlp", cfg.YT_DLP_BIN
    assert cfg.EXTRA_PATHS == ["/usr/local/bin", "/opt/homebrew/bin"], cfg.EXTRA_PATHS
    assert cfg.WINDOW_GEOMETRY == "600x760", cfg.WINDOW_GEOMETRY
    assert ps.subprocess_flags() == {"start_new_session": True}
    print("TEST 6 PASSED: macOS behaviour unchanged")

    print("ALL TESTS PASSED")
finally:
    sys.platform = real_platform
