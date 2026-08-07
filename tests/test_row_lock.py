import sys
import time
import tempfile
import subprocess

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
downloader.validate_url = lambda *a, **k: True

real_start_download = downloader.start_download

def pump(app, timeout=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


app = gui.DownloaderApp()
row0 = app.tabs[0].url_rows[0]
row0.entry.insert(0, "https://youtube.com/watch?v=aaa")
row1 = app.tabs[0]._add_url_row()
row1.entry.insert(0, "https://youtube.com/watch?v=bbb")
pump(app)

def state_of(row):
    return (str(row.entry.cget("state")), str(row.playlist_items_entry.cget("state")), str(row.archive_check.cget("state")))

assert state_of(row0) == ("normal", "normal", "normal")
assert state_of(row1) == ("normal", "normal", "normal")
print("TEST 1 PASSED: rows start enabled")

# Use a real long-lived subprocess (sleep) so pending_downloads stays > 0 while we check state.
def fake_start(command, stdout_queue, stderr_queue, done_queue):
    return real_start_download([sys.executable, "-c", "import time; time.sleep(5)"], stdout_queue, stderr_queue, done_queue)

downloader.start_download = fake_start

with tempfile.TemporaryDirectory() as d:
    app.path_var.set(d)
    app.tabs[0].on_download()
    pump(app, 0.3)

    assert app.tabs[0].pending_downloads > 0, "expected a pending download"
    assert state_of(row0) == ("disabled", "disabled", "disabled"), state_of(row0)
    assert state_of(row1) == ("disabled", "disabled", "disabled"), state_of(row1)
    assert str(row0.entry.cget("cursor")) == "notallowed"
    assert str(row0.playlist_items_entry.cget("cursor")) == "notallowed"
    assert str(row0.archive_check.cget("cursor")) == "notallowed"
    print("TEST 2 PASSED: rows disabled with notallowed cursor while downloading")

    # Cancel to force completion and confirm re-enable.
    app.tabs[0].on_cancel()
    for _ in range(100):
        pump(app, 0.1)
        if app.tabs[0].pending_downloads == 0:
            break

    assert app.tabs[0].pending_downloads == 0
    assert state_of(row0) == ("normal", "normal", "normal"), state_of(row0)
    assert state_of(row1) == ("normal", "normal", "normal"), state_of(row1)
    assert str(row0.entry.cget("cursor")) == ""
    print("TEST 3 PASSED: rows re-enabled with default cursor once downloads finish")

print("ALL TESTS PASSED")
