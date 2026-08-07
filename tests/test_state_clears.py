"""The tab's ✓/✗ clear once the user empties that batch; the ● never does."""
import sys
import tempfile
import time

import os as _bootstrap_os
sys.path.insert(0, _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__))))
PROJECT_ROOT = _bootstrap_os.path.dirname(
    _bootstrap_os.path.dirname(_bootstrap_os.path.abspath(__file__)))

import os

import platform_support as _ps
_ps.settings_path = (lambda d=tempfile.mkdtemp(prefix="ytdlpgui-test-"):
                     os.path.join(d, "settings.json"))

import config
import download_tab
import downloader
import gui
import notifier

for _module in (notifier, gui.notifier, download_tab.notifier):
    _module.notify = lambda *a: None

real_start = downloader.start_download
exit_code = [0]


def fake_start(command, out_q, err_q, done_q):
    script = "" if exit_code[0] == 0 else "raise SystemExit(1)"
    return real_start([sys.executable, "-c", script], out_q, err_q, done_q)


downloader.start_download = fake_start


def pump(app, seconds=0.3):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


def finish(app, tab):
    tab.on_download()
    for _ in range(60):
        pump(app, 0.1)
        if not tab.is_busy():
            break
    pump(app, 0.3)


def label(app, tab):
    return app.notebook.tab(tab.frame, "text")


app = gui.DownloaderApp()
try:
    tab = app.tabs[0]
    with tempfile.TemporaryDirectory() as out_dir:
        app.path_var.set(out_dir)

        # --- 1. A successful batch shows the tick ---------------------------
        tab.url_rows[0].entry.insert(0, "https://example.com/a")
        pump(app, 0.2)
        finish(app, tab)
        assert tab.status() == "ok", tab.status()
        assert "✓" in label(app, tab), label(app, tab)
        print(f"TEST 1 PASSED: finished batch shows {label(app, tab)!r}")

        # --- 2. Clearing the only (unremovable) row drops the tick ----------
        tab.url_rows[0].entry.delete(0, "end")
        pump(app, 0.4)
        assert tab.status() == "idle", tab.status()
        assert "✓" not in label(app, tab), label(app, tab)
        assert label(app, tab) == "1", label(app, tab)
        print("TEST 2 PASSED: clearing the first row's URL removes the tick")

        # --- 3. Typing a NEW url must not resurrect the old tick ------------
        tab.url_rows[0].entry.insert(0, "https://example.com/brand-new")
        pump(app, 0.4)
        assert tab.status() == "idle", "a fresh URL must not inherit the old result"
        assert "✓" not in label(app, tab), label(app, tab)
        print("TEST 3 PASSED: a newly typed URL does not bring the tick back")

        # --- 4. Same with several rows: tick goes only when ALL are empty ---
        finish(app, tab)
        row2 = tab._add_url_row()
        row2.entry.insert(0, "https://example.com/b")
        pump(app, 0.3)
        finish(app, tab)
        assert tab.status() == "ok"
        assert "✓" in label(app, tab)

        # Emptying just one row is not enough while another still has a URL.
        row2.entry.delete(0, "end")
        pump(app, 0.4)
        assert tab.has_any_url(), "first row still holds a URL"
        assert "✓" in label(app, tab), f"tick should remain: {label(app, tab)!r}"
        print("TEST 4 PASSED: tick stays while any row still holds a URL")

        # --- 5. Emptying the last remaining URL clears it -------------------
        tab.url_rows[0].entry.delete(0, "end")
        pump(app, 0.4)
        assert not tab.has_any_url()
        assert tab.status() == "idle", tab.status()
        assert "✓" not in label(app, tab), label(app, tab)
        print("TEST 5 PASSED: emptying the last URL clears the tick")

        # --- 6. Removing rows (rather than clearing) also clears it ---------
        tab.url_rows[0].entry.insert(0, "https://example.com/c")
        pump(app, 0.2)
        extra = tab._add_url_row()
        extra.entry.insert(0, "https://example.com/d")
        pump(app, 0.3)
        finish(app, tab)
        assert "✓" in label(app, tab)

        tab._remove_url_row(extra)
        tab.url_rows[0].entry.delete(0, "end")
        pump(app, 0.4)
        assert tab.status() == "idle", tab.status()
        assert "✓" not in label(app, tab), label(app, tab)
        print("TEST 6 PASSED: removing rows then clearing the first also drops the tick")

        # --- 7. A FAILED batch also loses its ✗ when cleared ----------------
        exit_code[0] = 1
        tab.url_rows[0].entry.insert(0, "https://example.com/bad")
        pump(app, 0.2)
        finish(app, tab)
        assert tab.status() == "fail", tab.status()
        assert "✗" in label(app, tab), label(app, tab)

        tab.url_rows[0].entry.delete(0, "end")
        pump(app, 0.4)
        assert tab.status() == "idle", tab.status()
        assert "✗" not in label(app, tab), label(app, tab)
        assert label(app, tab) == "1", label(app, tab)
        print("TEST 7 PASSED: clearing URLs also removes the cross")

        # --- 8. A fresh URL does not resurrect the cross either -------------
        tab.url_rows[0].entry.insert(0, "https://example.com/after-failure")
        pump(app, 0.4)
        assert tab.status() == "idle", "a fresh URL must not inherit the old failure"
        assert "✗" not in label(app, tab), label(app, tab)
        print("TEST 8 PASSED: a newly typed URL does not bring the cross back")
        tab.url_rows[0].entry.delete(0, "end")
        pump(app, 0.3)

        # --- 9. The ● is NOT clearable: it must track real processes --------
        exit_code[0] = 0
        downloader.start_download = lambda c, o, e, d: real_start(
            [sys.executable, "-c", "import time; time.sleep(5)"], o, e, d
        )
        tab.url_rows[0].entry.insert(0, "https://example.com/slow")
        pump(app, 0.2)
        tab.on_download()
        pump(app, 0.4)
        assert tab.is_busy(), "expected the batch to be running"
        assert "●" in label(app, tab), label(app, tab)

        # The user cannot reach this state -- inputs are locked mid-download --
        assert str(tab.url_rows[0].entry.cget("state")) == "disabled", (
            "row inputs must be locked while downloading, which is what makes "
            "the ● unclearable in the first place"
        )

        # ...and even forcing the value empty must not drop the busy state,
        # because pending_downloads also governs whether the tab may close.
        tab.url_rows[0].url_var.set("")
        pump(app, 0.4)
        assert tab.is_busy(), "busy state must survive an emptied URL"
        assert "●" in label(app, tab), f"● must persist while running: {label(app, tab)!r}"
        assert app.close_tab(tab) is False or tab in app.tabs
        print("TEST 9 PASSED: ● survives clearing and keeps tracking real processes")

        tab.on_cancel()
        for _ in range(100):
            pump(app, 0.1)
            if not tab.is_busy():
                break

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
