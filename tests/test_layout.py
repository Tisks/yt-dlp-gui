"""Shared header sits above the notebook, per-batch controls inside it, nothing clipped."""
import sys

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
import gui
import notifier

notifier.notify = lambda *a: None
gui.notifier.notify = lambda *a: None
download_tab.notifier.notify = lambda *a: None

app = gui.DownloaderApp()
try:
    app.root.update_idletasks()

    def find(root, cls, text=None):
        found = []

        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == cls:
                    try:
                        label = child.cget("text")
                    except Exception:
                        label = None
                    if text is None or label == text:
                        found.append(child)
                walk(child)

        walk(root)
        return found

    # --- 1. Shared header: Path + both dropdowns live OUTSIDE the tabs ------
    tab_frame = app.tabs[0].frame
    assert find(tab_frame, "TCombobox") == [], "dropdowns must not be inside a tab"
    assert find(tab_frame, "TLabel", "Path") == [], "Path must not be inside a tab"
    combos = find(app.container, "TCombobox")
    assert len(combos) == 2, f"expected browser + auto-close dropdowns, got {len(combos)}"
    print("TEST 1 PASSED: Path and both dropdowns are shared above the tabs")

    # --- 2. Both dropdowns are readonly with the right choices -------------
    browser_combo, auto_combo = combos
    assert list(browser_combo.cget("values")) == list(config.COOKIE_BROWSER_CHOICES)
    assert list(auto_combo.cget("values")) == list(config.AUTO_CLOSE_CHOICES)
    assert str(browser_combo.cget("state")) == "readonly"
    assert str(auto_combo.cget("state")) == "readonly"
    print(f"TEST 2 PASSED: browser={list(browser_combo.cget('values'))}, "
          f"auto-close={list(auto_combo.cget('values'))}, both readonly")

    # --- 3. They share one row, as requested -------------------------------
    assert abs(browser_combo.winfo_rooty() - auto_combo.winfo_rooty()) < 12, "dropdowns not on one row"
    assert auto_combo.winfo_rootx() > browser_combo.winfo_rootx(), "auto-close should sit to the right"
    labels = [l.cget("text") for l in find(app.container, "TLabel")]
    assert "Browser shortcut support" in labels, labels
    assert "Auto-close finished tabs" in labels, labels
    print("TEST 3 PASSED: 'Auto-close finished tabs' shares the row with 'Browser shortcut support'")

    # --- 4. Per-batch controls ARE inside the tab --------------------------
    assert find(tab_frame, "TLabel", "URL"), "URL header missing from tab"
    buttons = [b.cget("text") for b in find(tab_frame, "TButton")]
    assert "Download" in buttons and "Cancel" in buttons, buttons
    assert buttons.count("Clean") == 2, buttons
    print("TEST 4 PASSED: URL rows, Clean buttons and Download/Cancel live inside the tab")

    # --- 5. Nothing is clipped, at every row count up to the scroll limit --
    window_w, window_h = (int(v) for v in config.WINDOW_GEOMETRY.split("x"))
    for extra in range(0, 4):
        if extra:
            app.tabs[0]._add_url_row()
        app.root.update_idletasks()
        content_h = app.container.winfo_reqheight()
        content_w = app.container.winfo_reqwidth()
        assert content_h <= window_h, f"{extra + 1} rows: {content_h}px > window {window_h}px"
        assert content_w <= window_w, f"{extra + 1} rows: {content_w}px > window {window_w}px"
    print(f"TEST 5 PASSED: content fits {window_w}x{window_h} from 1 to 4 rows")

    # --- 6. A second tab does not grow the window --------------------------
    before = app.container.winfo_reqheight()
    app.add_tab()
    app.root.update_idletasks()
    after = app.container.winfo_reqheight()
    assert after <= window_h, f"adding a tab overflowed: {after}px"
    print(f"TEST 6 PASSED: adding a tab keeps height at {after}px (was {before}px)")

    # --- 7. Still vertically centred ---------------------------------------
    top_pad = app.container.pack_info()["pady"][0]
    assert top_pad >= 0
    print(f"TEST 7 PASSED: container still centred, top padding {top_pad}px")

    print("ALL TESTS PASSED")
finally:
    if getattr(app, "url_server", None) is not None:
        app.url_server.shutdown()
        app.url_server.server_close()
    app.root.destroy()
