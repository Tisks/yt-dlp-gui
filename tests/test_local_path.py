"""Per-tab 'Local path': the +/_ toggle, override semantics and its own error label."""
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

notified = []
for _module in (notifier, gui.notifier, download_tab.notifier):
    _module.notify = lambda title, message: notified.append(message)
downloader.validate_url = lambda *a, **k: True

started = []


def fake_start(command, *a):
    started.append(command)

    class P:
        pid = 1

    return P()


downloader.start_download = fake_start


def pump(app, seconds=0.25):
    deadline = time.time() + seconds
    while time.time() < deadline:
        app.root.update()
        time.sleep(0.02)


def path_of(command):
    return command[command.index("-P") + 1]


app = gui.DownloaderApp()
try:
    tab = app.tabs[0]
    tab.url_rows[0].entry.insert(0, "https://example.com/x")
    pump(app)

    # --- 1. Starts collapsed, showing '+' -------------------------------------
    assert tab.local_path_expanded is False
    assert tab.local_path_toggle.cget("text") == "+", tab.local_path_toggle.cget("text")
    assert not tab.local_path_entry.winfo_ismapped(), "field must start hidden"
    print("TEST 1 PASSED: starts collapsed with a '+' glyph and no field")

    # --- 2. Clicking expands and swaps the glyph to '_' -----------------------
    app.root.update_idletasks()
    width_collapsed = app.container.winfo_reqwidth()
    tab.toggle_local_path()
    app.root.update_idletasks()
    assert tab.local_path_expanded is True
    assert tab.local_path_toggle.cget("text") == "_", tab.local_path_toggle.cget("text")
    assert tab.local_path_entry.winfo_ismapped(), "field must be visible once expanded"
    print("TEST 2 PASSED: '+' expands the field and becomes '_'")

    # --- 2b. Expanding must not widen the tab --------------------------------
    width_expanded = app.container.winfo_reqwidth()
    assert width_expanded <= width_collapsed, (
        f"showing the local path widened the tab: {width_collapsed} -> {width_expanded}"
    )
    print(f"TEST 2b PASSED: tab width unchanged at {width_expanded}px when expanded")

    # --- 2c. The field is left-aligned, not centred --------------------------
    label_x = tab.local_path_toggle.master.winfo_rootx()
    entry_x = tab.local_path_entry.winfo_rootx()
    assert abs(entry_x - label_x) <= 2, (
        f"local path field is not left-aligned: label at {label_x}, field at {entry_x}"
    )
    print(f"TEST 2c PASSED: field left-aligned with the label (both at x={entry_x})")

    # --- 3. Collapsing hides the field but keeps the typed value --------------
    with tempfile.TemporaryDirectory() as local_dir:
        tab.local_path_var.set(local_dir)
        tab.toggle_local_path()
        app.root.update_idletasks()
        assert tab.local_path_expanded is False
        assert tab.local_path_toggle.cget("text") == "+"
        assert not tab.local_path_entry.winfo_ismapped(), "field must be hidden again"
        assert tab.local_path_var.get() == local_dir, "value must survive collapsing"
        print("TEST 3 PASSED: '_' hides the field but keeps the string")

        # --- 4. A collapsed-but-filled local path still overrides ------------
        with tempfile.TemporaryDirectory() as shared_dir:
            app.path_var.set(shared_dir)
            started.clear()
            tab.on_download()
            pump(app)
            assert started, "expected a download to start"
            assert path_of(started[0]) == local_dir, path_of(started[0])
            print("TEST 4 PASSED: local path overrides the shared Path even when collapsed")

            # --- 5. Blank local path falls back to the shared Path ----------
            tab.local_path_var.set("")
            tab.pending_downloads = 0
            started.clear()
            tab.on_download()
            pump(app)
            assert path_of(started[0]) == shared_dir, path_of(started[0])
            print("TEST 5 PASSED: blank local path defers to the shared Path")

    # --- 6. A bad local path reports on ITS OWN label, not the shared one -----
    with tempfile.TemporaryDirectory() as shared_dir:
        app.path_var.set(shared_dir)
        tab.local_path_var.set(os.path.join(shared_dir, "does-not-exist"))
        tab.pending_downloads = 0
        started.clear()
        notified.clear()
        tab.on_download()
        pump(app)
        assert not started, "download must not start with an invalid local path"
        assert tab.local_path_message.cget("text") == "Path doesn't exist", (
            tab.local_path_message.cget("text")
        )
        assert tab.message_label.cget("text") == "", "shared label must stay clean"
        assert "Path doesn't exist" in notified, notified
        print("TEST 6 PASSED: invalid local path errors on the Local path label only")

        # --- 7. The error survives collapsing, moving up under the label ----
        tab.toggle_local_path()  # expand
        tab.toggle_local_path()  # collapse again
        app.root.update_idletasks()
        assert tab.local_path_message.cget("text") == "Path doesn't exist", "error must persist"
        assert tab.local_path_message.winfo_ismapped(), "error must stay visible when collapsed"
        assert not tab.local_path_entry.winfo_ismapped()
        assert tab.local_path_message.winfo_rooty() < tab.url_rows[0].entry.winfo_rooty()
        print("TEST 7 PASSED: error stays visible and rises under 'Local path' when collapsed")

        # --- 8. Typing clears the local error -------------------------------
        tab.local_path_var.set(shared_dir)
        app.root.update_idletasks()
        assert tab.local_path_message.cget("text") == "", "editing should clear the warning"
        print("TEST 8 PASSED: editing the local path clears its warning")

    # --- 9. A local path pointing at a FILE is rejected too ------------------
    with tempfile.TemporaryDirectory() as shared_dir:
        file_path = os.path.join(shared_dir, "a-file.txt")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("x")
        app.path_var.set(shared_dir)
        tab.local_path_var.set(file_path)
        tab.pending_downloads = 0
        started.clear()
        tab.on_download()
        pump(app)
        assert not started
        assert tab.local_path_message.cget("text") == "Path points to a file instead of a folder"
        print("TEST 9 PASSED: a local path pointing at a file is rejected")

    # --- 10. Blank local + blank shared complains about the SHARED field -----
    tab.local_path_var.set("")
    app.path_var.set("")
    tab.pending_downloads = 0
    started.clear()
    tab.on_download()
    pump(app)
    assert not started
    assert tab.message_label.cget("text") == "Empty download path", tab.message_label.cget("text")
    assert tab.local_path_message.cget("text") == "", "blank local path is never an error"
    print("TEST 10 PASSED: blank local path is ignored; empty shared Path is the error")

    # --- 11. The download shortcut goes through the same validation ----------
    with tempfile.TemporaryDirectory() as shared_dir:
        app.path_var.set(shared_dir)
        tab.local_path_var.set(os.path.join(shared_dir, "nope"))
        tab.pending_downloads = 0
        started.clear()
        app.download_trigger_queue.put(True)
        pump(app, 0.4)
        assert not started, "shortcut must respect the local path error"
        assert tab.local_path_message.cget("text") == "Path doesn't exist"
        print("TEST 11 PASSED: the download shortcut honours the local path error")

    # --- 12. Local paths are per tab, not shared -----------------------------
    tab2 = app.add_tab()
    assert tab2.local_path_var.get() == "", "a new tab starts with its own blank local path"
    assert tab2.local_path_expanded is False
    with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
        tab.local_path_var.set(dir_a)
        tab2.local_path_var.set(dir_b)
        assert tab.local_path_var.get() == dir_a
        assert tab2.local_path_var.get() == dir_b
        print("TEST 12 PASSED: each tab keeps its own local path")

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
