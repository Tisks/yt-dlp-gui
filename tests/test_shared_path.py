import sys
import time
import tempfile
import os

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

# Keep tests off the real settings file.
import os as _os, tempfile as _tempfile
import platform_support as _ps
_ps.settings_path = (lambda d=_tempfile.mkdtemp(prefix="ytdlpgui-test-"):
                     _os.path.join(d, "settings.json"))

import downloader
import gui
import notifier

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None

started_commands = []
def fake_start(command, *a):
    started_commands.append(command)
    class P:
        pid = 1
    return P()

downloader.start_download = fake_start


def pump(app, timeout=0.3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


app = gui.DownloaderApp()

# Empty path should now block even an archive-mode-only download (no more hardcoded fallback).
app.tabs[0].url_rows[0].entry.insert(0, "https://youtube.com/channel/xyz")
app.tabs[0].url_rows[0].archive_var.set(True)
app.path_var.set("")
pump(app)
started_commands.clear()
app.tabs[0].on_download()
pump(app)
assert not started_commands, "archive-mode download should now require a valid path too"
assert app.tabs[0].message_label.cget("text") == "Empty download path"
print("TEST 1 PASSED: archive-mode entries now require the Path field to be valid")

# With a valid path, archive mode should use it for -P and for the archive.txt location.
with tempfile.TemporaryDirectory() as tmp_dir:
    app.path_var.set(tmp_dir)
    started_commands.clear()
    app.tabs[0].on_download()
    pump(app)

    assert started_commands, "expected the archive-mode command to start"
    command = started_commands[0]
    p_index = command.index("-P")
    assert command[p_index + 1] == tmp_dir, command
    archive_index = command.index("--download-archive")
    expected_archive_file = os.path.join(tmp_dir, "archive.txt")
    assert command[archive_index + 1] == expected_archive_file, command[archive_index + 1]
    print("TEST 2 PASSED: archive-mode command uses the Path field for -P and archive.txt location")

print("ALL TESTS PASSED")
