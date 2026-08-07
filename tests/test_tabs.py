"""Tab lifecycle: creation, the '+' tab, closing, status labels, routing, auto-close."""
import sys
import tempfile
import time

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

import config
import download_tab
import downloader
import gui
import notifier

notified = []
notifier.notify = lambda title, message: notified.append(message)
gui.notifier.notify = lambda title, message: notified.append(message)
download_tab.notifier.notify = lambda title, message: notified.append(message)

real_start_download = downloader.start_download


def fake_start(command, stdout_queue, stderr_queue, done_queue):
    return real_start_download([sys.executable, "-c", "import time; time.sleep(5)"], stdout_queue, stderr_queue, done_queue)


downloader.start_download = fake_start


def pump(app, seconds=0.3):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


app = gui.DownloaderApp()
try:
    # --- 1. Starts with one batch tab plus the '+' tab ---------------------
    assert len(app.tabs) == 1, len(app.tabs)
    assert app.notebook.index("end") == 2, "expected batch tab + '+' tab"
    assert app.notebook.tab(app.plus_frame, "text") == gui.PLUS_TAB_TEXT
    assert app.active_tab() is app.tabs[0]
    print("TEST 1 PASSED: opens with tab 1 and a '+' tab")

    # --- 2. First tab has no close glyph; label shows no status when idle --
    label0 = app.notebook.tab(app.tabs[0].frame, "text")
    assert label0 == "1", repr(label0)
    assert gui.CLOSE_GLYPH not in label0, "first tab must not be closable"
    print(f"TEST 2 PASSED: first tab label is {label0!r} with no close glyph")

    # --- 3. Selecting '+' creates a real batch tab and selects it ----------
    app.notebook.select(app.plus_frame)
    pump(app, 0.2)
    assert len(app.tabs) == 2, len(app.tabs)
    assert app.active_tab() is app.tabs[1], "new tab should become active"
    assert app.notebook.select() != str(app.plus_frame), "'+' must never stay selected"
    label1 = app.notebook.tab(app.tabs[1].frame, "text")
    assert gui.CLOSE_GLYPH in label1, repr(label1)
    print(f"TEST 3 PASSED: '+' spawned {label1!r} and selected it")

    # --- 4. '+' stays last, after every real tab ---------------------------
    assert app.notebook.index(app.plus_frame) == len(app.tabs), "'+' must remain the last tab"
    print("TEST 4 PASSED: '+' tab stays at the end")

    # --- 5. Tabs are independent: rows added to one don't appear in another
    app.tabs[0].url_rows[0].entry.insert(0, "https://example.com/in-tab-1")
    app.tabs[1].url_rows[0].entry.insert(0, "https://example.com/in-tab-2")
    pump(app)
    assert app.tabs[0].url_rows[0].entry.get() == "https://example.com/in-tab-1"
    assert app.tabs[1].url_rows[0].entry.get() == "https://example.com/in-tab-2"
    assert app.tabs[0].output_text is not app.tabs[1].output_text
    print("TEST 5 PASSED: rows and output boxes are per tab")

    # --- 6. Downloading in tab 2 leaves tab 1 fully usable -----------------
    with tempfile.TemporaryDirectory() as tmp_dir:
        app.path_var.set(tmp_dir)
        app.notebook.select(app.tabs[1].frame)
        app.tabs[1].on_download()
        pump(app, 0.3)

        assert app.tabs[1].is_busy(), "tab 2 should be downloading"
        assert not app.tabs[0].is_busy(), "tab 1 must be unaffected"
        assert str(app.tabs[0].url_rows[0].entry.cget("state")) == "normal", "tab 1 inputs must stay enabled"
        assert str(app.tabs[1].url_rows[0].entry.cget("state")) == "disabled", "tab 2 inputs must lock"
        print("TEST 6 PASSED: tab 2 downloading leaves tab 1 unlocked")

        # --- 7. Busy tab shows the ● status glyph in its label -------------
        app._update_tab_labels()
        busy_label = app.notebook.tab(app.tabs[1].frame, "text")
        assert "●" in busy_label, repr(busy_label)
        idle_label = app.notebook.tab(app.tabs[0].frame, "text")
        assert "●" not in idle_label, repr(idle_label)
        print(f"TEST 7 PASSED: busy tab reads {busy_label!r}, idle reads {idle_label!r}")

        # --- 8. Extension URL routed to a busy active tab warns ------------
        notified.clear()
        app.url_queue.put(("https://example.com/new", "chrome"))
        pump(app, 0.3)
        assert download_tab.TAB_BUSY_MESSAGE in notified, notified
        print(f"TEST 8 PASSED: busy tab alerts {download_tab.TAB_BUSY_MESSAGE!r}")

        # --- 9. Same URL routed to an idle tab lands normally --------------
        notified.clear()
        app.notebook.select(app.tabs[0].frame)
        pump(app, 0.1)
        rows_before = len(app.tabs[0].url_rows)
        app.url_queue.put(("https://example.com/new", "firefox"))
        pump(app, 0.3)
        assert "URL added" in notified, notified
        assert len(app.tabs[0].url_rows) == rows_before + 1, len(app.tabs[0].url_rows)
        assert download_tab.TAB_BUSY_MESSAGE not in notified
        print("TEST 9 PASSED: switching tabs lets the shortcut work again")

        # --- 10. A busy tab refuses to close -------------------------------
        assert app.close_tab(app.tabs[1]) is False, "busy tab must not close"
        assert len(app.tabs) == 2
        print("TEST 10 PASSED: busy tab cannot be closed")

        # Stop the download so the rest can proceed.
        app.tabs[1].on_cancel()
        for _ in range(100):
            pump(app, 0.1)
            if not app.tabs[1].is_busy():
                break
        assert not app.tabs[1].is_busy()

    # --- 11. An idle non-first tab closes, and '+' is never left selected --
    assert app.close_tab(app.tabs[1]) is True
    assert len(app.tabs) == 1, len(app.tabs)
    assert app.notebook.select() != str(app.plus_frame)
    assert app.active_tab() is app.tabs[0]
    print("TEST 11 PASSED: idle tab closes and selection lands on a real tab")

    # --- 12. First tab still refuses to close ------------------------------
    assert app.close_tab(app.tabs[0]) is False
    assert len(app.tabs) == 1
    print("TEST 12 PASSED: first tab is permanent")

    # --- 13. Labels do NOT renumber after a close --------------------------
    # Closing the middle of a-b-c must leave a-c, not silently rename c to b:
    # the label has to keep matching the logs the user is looking at.
    def numbers(app):
        return [int(app.notebook.tab(t.frame, "text").split()[0]) for t in app.tabs]

    while len(app.tabs) > 1:
        app.close_tab(app.tabs[-1])
    first, middle, last = app.tabs[0], app.add_tab(), app.add_tab()
    app._update_tab_labels()
    before = numbers(app)
    assert before == [first.number, middle.number, last.number], before
    assert before == sorted(before) and len(set(before)) == 3, before

    app.close_tab(middle)
    app._update_tab_labels()
    after = numbers(app)
    assert after == [first.number, last.number], (before, after)
    print(f"TEST 13 PASSED: closing the middle of {before} leaves {after}, no renumbering")

    # --- 14. A number is never reused once handed out ----------------------
    fresh = app.add_tab()
    app._update_tab_labels()
    assert fresh.number > max(before), (fresh.number, before)
    assert middle.number not in numbers(app), (
        f"the freed number {middle.number} was reused: {numbers(app)}"
    )
    print(f"TEST 14 PASSED: freed number {middle.number} not reused -> {numbers(app)}")

    # --- 15. Numbering follows the open tabs, not a running total ----------
    # Open 30 and close them all: the next tab must be 2, not 31.
    while len(app.tabs) > 1:
        app.close_tab(app.tabs[-1])
    app._update_tab_labels()
    assert numbers(app) == [1], numbers(app)
    for _ in range(30):
        app.add_tab()
    app._update_tab_labels()
    assert numbers(app) == list(range(1, 32)), numbers(app)
    while len(app.tabs) > 1:
        app.close_tab(app.tabs[-1])
    reopened = app.add_tab()
    app._update_tab_labels()
    assert reopened.number == 2, f"expected 2 after closing 30 tabs, got {reopened.number}"
    assert numbers(app) == [1, 2], numbers(app)
    print("TEST 15 PASSED: after opening and closing 30 tabs the next one is 2")

    # --- 16. A gap below the rightmost tab is not backfilled ---------------
    # 1-2 -> add 3 -> close 2 -> add must be 4, keeping numbers ascending.
    third = app.add_tab()
    app.close_tab(app.tabs[1])
    app._update_tab_labels()
    assert numbers(app) == [1, 3], numbers(app)
    fourth = app.add_tab()
    app._update_tab_labels()
    assert fourth.number == 4, fourth.number
    assert numbers(app) == [1, 3, 4], numbers(app)
    print(f"TEST 16 PASSED: gap at 2 left alone, next tab is {fourth.number} -> {numbers(app)}")

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
