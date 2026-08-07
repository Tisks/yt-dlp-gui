import os
import queue
import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog

import config
import download_tab
from core import tabstrip
import notifier
import platform_support
import settings
import url_server

from download_tab import (  # re-exported so tests and callers keep one import site
    MAX_VISIBLE_ROWS,
    PLAYLIST_ITEMS_PLACEHOLDER,
    PLACEHOLDER_FG,
    TAB_BUSY_MESSAGE,
)

PLUS_TAB_TEXT = "  +  "
CLOSE_GLYPH = "✕"
# How far from a tab's right edge a click still counts as hitting the ✕.
# macOS Aqua ignores custom ttk tab elements, so the glyph lives in the tab
# text and we hit-test the region ourselves.
CLOSE_ZONE_PX = 22

STATUS_GLYPH = {"idle": "", "busy": "●", "ok": "✓", "fail": "✗"}

# Aqua gives a ttk.Notebook no tab overflow of its own: the strip just grows
# until the tabs run off the window. We page through them instead, showing a
# fixed-size window of tabs and hiding the rest. Eight is what fits alongside
# the '+' tab in the default geometry once labels are just the batch number.
TABS_PER_PAGE = 8
# Overlap one tab per page turn so there is a shared landmark between pages.
PAGER_STEP = TABS_PER_PAGE - 1
PAGER_PREV_GLYPH = "‹"
PAGER_NEXT_GLYPH = "›"
# Keeps the notebook from jumping when the pager appears at the 9th tab.
PAGER_ROW_HEIGHT = 22


class DownloaderApp:
    def __init__(self):
        self.url_queue = queue.Queue()
        self.download_trigger_queue = queue.Queue()
        self.check_archive_trigger_queue = queue.Queue()

        self.tabs = []
        # ttk delivers <<NotebookTabChanged>> asynchronously, so a plain
        # try/finally guard is already reset by the time the event lands. This
        # latch is instead held until the spawned tab actually exists.
        self._spawn_pending = False

        # Index of the leftmost tab on the current page, plus caches so the
        # 100ms poll only touches widgets when the visible set really changed.
        self.page_start = 0
        self._visible_span = None
        self._pager_shown = None

        # The floating window used to rename a tab in place; see _start_rename.
        self._rename_window = None
        self._rename_entry = None
        self._rename_tab = None

        self.settings = settings.load()

        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_GEOMETRY)
        self._bind_close_handlers()

        self.frame_bg = ttk.Style().lookup("TFrame", "background") or "systemWindowBackgroundColor"

        self._build_widgets()
        self._center_container_initially()
        self._start_url_server()
        self._poll()

    # ------------------------------------------------------------- lifecycle

    def _bind_close_handlers(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if platform_support.IS_MACOS:
            # Cmd-Q and the Quit apple event bypass WM_DELETE_WINDOW on macOS.
            try:
                self.root.createcommand("::tk::mac::Quit", self._on_close)
            except tk.TclError:
                pass

    def _on_close(self):
        self.save_settings()
        self.root.destroy()

    def save_settings(self):
        # Only ever persist a folder that exists, so a half-typed path can't
        # replace a known-good one; otherwise keep what was already saved.
        path = self.path_var.get().strip()
        if not os.path.isdir(path):
            path = self.settings.get("path", "")

        self.settings = {
            "path": path,
            "cookies_browser": self.cookies_browser_var.get(),
            "auto_close_tabs": self.auto_close_var.get(),
        }
        settings.save(**self.settings)

    def _center_container_initially(self):
        self.root.update_idletasks()
        _width, window_height = (int(value) for value in config.WINDOW_GEOMETRY.split("x"))
        content_height = self.container.winfo_reqheight()
        top_pad = max(0, (window_height - content_height) // 2)
        self.container.pack_configure(pady=(top_pad, 0))

    def run(self):
        self.root.mainloop()

    # --------------------------------------------------------------- widgets

    def _build_widgets(self):
        container = ttk.Frame(self.root, padding=20)
        container.pack(expand=True, anchor="n")
        self.container = container

        ttk.Label(container, text="Path").pack(pady=(0, 4), fill="x", anchor="w")

        self.path_var = tk.StringVar(value=self.settings["path"])
        path_entry = ttk.Entry(container, textvariable=self.path_var, width=52)
        path_entry.pack(pady=(0, 4))
        self.path_var.trace_add("write", lambda *_args: self._clear_tab_messages())

        options_row = ttk.Frame(container)
        options_row.pack(pady=(0, 8), fill="x")

        ttk.Label(options_row, text="Browser shortcut support").pack(side="left")
        self.cookies_browser_var = tk.StringVar(value=self.settings["cookies_browser"])
        ttk.Combobox(
            options_row,
            textvariable=self.cookies_browser_var,
            values=config.COOKIE_BROWSER_CHOICES,
            state="readonly",
            width=9,
            cursor=platform_support.CURSOR_CLICKABLE,
        ).pack(side="left", padx=(6, 0))

        ttk.Label(options_row, text="Auto-close finished tabs").pack(side="left", padx=(16, 0))
        self.auto_close_var = tk.StringVar(value=self.settings["auto_close_tabs"])
        ttk.Combobox(
            options_row,
            textvariable=self.auto_close_var,
            values=config.AUTO_CLOSE_CHOICES,
            state="readonly",
            width=5,
            cursor=platform_support.CURSOR_CLICKABLE,
        ).pack(side="left", padx=(6, 0))

        # Tk offers no way to put widgets inside a notebook's tab strip, so the
        # pager sits in its own row directly above it. The row keeps its height
        # whether or not the arrows are showing, so revealing them at the 9th
        # tab does not shove the notebook down.
        self.pager_row = ttk.Frame(container, height=PAGER_ROW_HEIGHT)
        self.pager_row.pack(fill="x")
        self.pager_row.pack_propagate(False)

        self.pager_range = ttk.Label(self.pager_row, style="Pager.TLabel")
        self.pager_next = ttk.Label(
            self.pager_row, text=PAGER_NEXT_GLYPH, font=("", 15), cursor=platform_support.CURSOR_CLICKABLE
        )
        self.pager_prev = ttk.Label(
            self.pager_row, text=PAGER_PREV_GLYPH, font=("", 15), cursor=platform_support.CURSOR_CLICKABLE
        )
        self.pager_prev.bind("<Button-1>", lambda _event: self._page_by(-PAGER_STEP))
        self.pager_next.bind("<Button-1>", lambda _event: self._page_by(PAGER_STEP))

        # Muted, so the off-page count reads as an annotation rather than a label.
        ttk.Style().configure(
            "Pager.TLabel", foreground=ttk.Style().lookup("TLabel", "foreground", ["disabled"])
        )

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)

        # A real tab used purely as a "new batch" button. Selecting it is
        # detectable, which is the only way to get a + affordance in ttk.
        self.plus_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.plus_frame, text=PLUS_TAB_TEXT)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.notebook.bind("<Button-1>", self._on_notebook_click, add="+")
        self.notebook.bind("<Double-Button-1>", self._on_notebook_double_click, add="+")
        self.notebook.bind("<Motion>", self._on_notebook_motion, add="+")
        self.notebook.bind("<Leave>", lambda _event: self.notebook.config(cursor=""), add="+")

        self.add_tab()

    def _clear_tab_messages(self):
        for tab in self.tabs:
            tab.message_label.config(text="")

    # ---------------------------------------------------------- tab handling

    def add_tab(self):
        tab = download_tab.DownloadTab(self, self.notebook)
        tab.number = self._next_tab_number()
        plus_index = self.notebook.index(self.plus_frame)
        self.notebook.insert(plus_index, tab.frame, text="")
        self.tabs.append(tab)
        self._select_tab(tab)
        return tab

    def _next_tab_number(self):
        return tabstrip.next_tab_number([tab.number for tab in self.tabs])

    def _select_tab(self, tab):
        """Select a tab, paging to it first if it is currently off-screen."""
        # A hidden tab cannot be selected, and a tab added past TABS_PER_PAGE
        # lands off-page. add() is a no-op on an already-visible tab.
        self.notebook.add(tab.frame)
        self.notebook.select(tab.frame)
        self._visible_span = None  # force a re-render around the new selection
        self._update_tab_labels()

    def close_tab(self, tab):
        if tab not in self.tabs:
            return False
        if self.tabs.index(tab) == 0:
            return False  # the first tab is permanent, so there is always a landing spot
        if tab.is_busy():
            notifier.notify(config.APP_NAME, TAB_BUSY_MESSAGE)
            return False

        if tab is self._rename_tab:
            self._cancel_rename()

        index = self.tabs.index(tab)
        self.tabs.remove(tab)
        self.notebook.forget(tab.frame)
        tab.destroy()

        # Never leave the '+' tab selected, or it would spawn a tab immediately.
        self._select_tab(self.tabs[min(index, len(self.tabs) - 1)])
        return True

    def active_tab(self):
        selected = self.notebook.select()
        for tab in self.tabs:
            if str(tab.frame) == selected:
                return tab
        return self.tabs[0] if self.tabs else None

    def _update_tab_labels(self):
        # Hide/show first: a tab's text survives add(), so paging cannot undo
        # the labels, and this way a freshly revealed tab is never left blank.
        self._render_tab_page()
        for index, tab in enumerate(self.tabs):
            # tab.number, not the position, so closing a tab renames nothing.
            label = tabstrip.tab_label(
                tab.number, STATUS_GLYPH[tab.status()], closable=index > 0,
                close_glyph=CLOSE_GLYPH, name=tab.custom_name,
            )
            self.notebook.tab(tab.frame, text=label)

    # ----------------------------------------------------------- tab paging

    def _selected_index(self):
        """Index into self.tabs of the selected tab, or None for the '+' tab."""
        selected = self.notebook.select()
        for index, tab in enumerate(self.tabs):
            if str(tab.frame) == selected:
                return index
        return None

    def _visible_window(self, total):
        """The (start, end) slice of self.tabs that should be on screen."""
        return tabstrip.visible_window(
            total, self.page_start, self._selected_index(), TABS_PER_PAGE
        )

    def _render_tab_page(self):
        total = len(self.tabs)
        start, end = self._visible_window(total)
        self.page_start = start

        # Runs on every 100ms poll, so only touch ttk when something moved.
        if self._visible_span != (start, end, total):
            self._visible_span = (start, end, total)
            for index, tab in enumerate(self.tabs):
                if start <= index < end:
                    self.notebook.add(tab.frame)
                else:
                    self.notebook.hide(tab.frame)

        self._update_pager(start, end, total)

    def _update_pager(self, start, end, total):
        needed = total > TABS_PER_PAGE
        if needed != self._pager_shown:
            self._pager_shown = needed
            if needed:
                # Packed right to left so the arrows sit inside the count.
                self.pager_range.pack(side="right", padx=(0, 2))
                self.pager_next.pack(side="right", padx=(2, 8))
                self.pager_prev.pack(side="right")
            else:
                for widget in (self.pager_range, self.pager_next, self.pager_prev):
                    widget.pack_forget()
        if not needed:
            return

        self.pager_range.config(text=tabstrip.offscreen_text(start, end, total))

        # ttk greys a disabled label using the theme's own colour, which keeps
        # this readable in both light and dark mode.
        self.pager_prev.state(["!disabled"] if start else ["disabled"])
        self.pager_next.state(["!disabled"] if end < total else ["disabled"])

    def _page_by(self, delta):
        self._commit_rename()  # the overlay's position would go stale on a new page
        total = len(self.tabs)
        if total <= TABS_PER_PAGE:
            return
        direction = 1 if delta > 0 else -1
        self.page_start = tabstrip.turn_page(self.page_start, direction, total, TABS_PER_PAGE)

        # Move the selection onto the page rather than letting _visible_window
        # immediately drag the page back to wherever the selection still is.
        landing = tabstrip.landing_index(
            self._selected_index(), self.page_start, self.page_start + TABS_PER_PAGE
        )
        if landing is not None:
            self.notebook.select(self.tabs[landing].frame)
        self._update_tab_labels()

    def _on_tab_changed(self, event=None):
        if self._spawn_pending:
            return
        selected = self.notebook.select()
        if selected and selected == str(self.plus_frame):
            # Selecting '+' means "new batch"; swap to a real tab immediately.
            self._spawn_pending = True
            self.root.after_idle(self._spawn_tab_from_plus)

    def _spawn_tab_from_plus(self):
        try:
            self.add_tab()
        finally:
            self._spawn_pending = False

    def _on_notebook_click(self, event):
        tab = self._tab_close_hit(event)
        if tab is None:
            return None
        # Destroying widgets inside the click handler upsets ttk, so defer.
        self.root.after_idle(lambda: self.close_tab(tab))
        return "break"

    def _on_notebook_motion(self, event):
        try:
            index = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            index = None

        if index is not None and index == self.notebook.index(self.plus_frame):
            cursor = platform_support.CURSOR_CLICKABLE
        elif self._tab_close_hit(event) is not None:
            cursor = platform_support.CURSOR_CLICKABLE
        elif index is not None and 0 <= index < len(self.tabs):
            # The label body is what double-click renames -- CURSOR_TEXT signals
            # that, the same way the URL entries do for typing.
            cursor = platform_support.CURSOR_TEXT
        else:
            cursor = ""
        self.notebook.config(cursor=cursor)

    def _tab_close_hit(self, event):
        """The tab whose ✕ was clicked, or None."""
        try:
            index = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return None
        if index <= 0 or index >= len(self.tabs):
            return None  # first tab has no ✕, and the '+' tab is not closable
        if not self._in_close_zone(event, index):
            return None
        return self.tabs[index]

    def _in_close_zone(self, event, index):
        """Whether `event` falls within CLOSE_ZONE_PX of the tab's right edge."""
        right_edge = event.x
        while right_edge - event.x < 400:
            try:
                if self.notebook.index(f"@{right_edge + 1},{event.y}") != index:
                    break
            except tk.TclError:
                break
            right_edge += 1
        return right_edge - event.x <= CLOSE_ZONE_PX

    def _tab_rename_hit(self, event):
        """The tab whose label body was double-clicked, or None."""
        try:
            index = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return None
        if index < 0 or index >= len(self.tabs):
            return None  # off the strip, or the '+' tab
        if index > 0 and self._in_close_zone(event, index):
            return None  # double-clicking the ✕ should not open a rename box
        return self.tabs[index]

    def _on_notebook_double_click(self, event):
        tab = self._tab_rename_hit(event)
        if tab is None:
            return None
        self._start_rename(tab, event)
        return "break"

    def _tab_screen_bbox(self, event, index):
        """The tab's on-screen bounding box, found by hand.

        ttk.Notebook.bbox() reports all zeros under this Aqua build, so like
        _in_close_zone above, the edges are found by hit-testing neighbouring
        pixels rather than trusted from the widget.
        """
        def horizontal_edge(step):
            pos = event.x
            for _ in range(400):
                probe = pos + step
                try:
                    if self.notebook.index(f"@{probe},{event.y}") != index:
                        return pos
                except tk.TclError:
                    return pos
                pos = probe
            return pos

        def vertical_edge(step):
            pos = event.y
            for _ in range(100):
                probe = pos + step
                try:
                    self.notebook.index(f"@{event.x},{probe}")
                except tk.TclError:
                    return pos
                pos = probe
            return pos

        left, right = horizontal_edge(-1), horizontal_edge(1)
        top, bottom = vertical_edge(-1), vertical_edge(1)
        screen_x = self.notebook.winfo_rootx() + left
        screen_y = self.notebook.winfo_rooty() + top
        return screen_x, screen_y, right - left + 1, bottom - top + 1

    def _start_rename(self, tab, event):
        self._commit_rename()  # save whatever was already being edited
        index = self.tabs.index(tab)
        screen_x, screen_y, width, height = self._tab_screen_bbox(event, index)

        # A child widget place()d onto the notebook itself would sit behind the
        # native Aqua tab strip -- the same reason the ✕ above is baked into the
        # tab text rather than a real button. A borderless Toplevel is a real
        # window, so macOS stacks it above the notebook like any other window.
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.transient(self.root)
        window.geometry(f"{width}x{height}+{screen_x}+{screen_y}")

        entry = tk.Entry(window)
        entry.pack(fill="both", expand=True)
        entry.insert(0, tab.custom_name or str(tab.number))
        entry.select_range(0, "end")
        window.lift()
        entry.focus_force()
        entry.bind("<Return>", lambda _event: self._commit_rename())
        entry.bind("<Escape>", lambda _event: self._cancel_rename())
        entry.bind("<FocusOut>", lambda _event: self._commit_rename())

        self._rename_window = window
        self._rename_entry = entry
        self._rename_tab = tab

    def _commit_rename(self):
        if self._rename_entry is None:
            return
        value = self._rename_entry.get().strip()
        tab = self._rename_tab
        self._destroy_rename_entry()
        if tab in self.tabs:
            tab.custom_name = value or None
            self._update_tab_labels()

    def _cancel_rename(self):
        self._destroy_rename_entry()

    def _destroy_rename_entry(self):
        if self._rename_entry is not None:
            self._rename_window.destroy()
            self._rename_window = None
            self._rename_entry = None
            self._rename_tab = None

    def _auto_close_finished_tabs(self):
        if self.auto_close_var.get() != config.AUTO_CLOSE_ON:
            return
        # Only successful batches: a failed one keeps its error log on screen.
        for tab in list(self.tabs[1:]):
            if tab.status() == "ok":
                self.close_tab(tab)

    # ------------------------------------------------------------ url server

    def _start_url_server(self):
        queues = (self.url_queue, self.download_trigger_queue, self.check_archive_trigger_queue)
        try:
            server = url_server.start_server(*queues)
        except OSError:
            server = self._start_url_server_on_custom_port(queues)

        self.url_server = server
        if server is None:
            self.server_port = None
            return

        self.server_port = server.server_port
        if self.server_port != config.URL_SERVER_PORT:
            self.tabs[0]._append_text(
                self.tabs[0].output_text, f"Browser extension port: {self.server_port}\n"
            )

    def _start_url_server_on_custom_port(self, queues):
        first, last = config.URL_SERVER_PORTS[0], config.URL_SERVER_PORTS[-1]
        while True:
            port = simpledialog.askinteger(
                "Port in use",
                f"Ports {first}-{last} are all in use.\n\n"
                "Enter another port to receive URLs on, or Cancel to run\n"
                "without the browser extension.\n\n"
                f"Note: the extension only scans {first}-{last}, so the browser\n"
                "shortcuts will not reach a port outside that range.",
                parent=self.root,
                minvalue=1024,
                maxvalue=65535,
            )
            if port is None:
                self.tabs[0]._append_text(
                    self.tabs[0].error_text,
                    "URL receiver not started: no free port. Browser shortcuts are disabled.\n",
                )
                return None
            try:
                return url_server.start_server(*queues, ports=[port])
            except OSError as exc:
                self.tabs[0]._append_text(self.tabs[0].error_text, f"Port {port} unavailable: {exc}\n")

    # ------------------------------------------------------------------ poll

    def _poll(self):
        for tab in list(self.tabs):
            tab.poll()

        self._poll_incoming_url()
        self._poll_download_trigger()
        self._poll_check_archive_trigger()

        self._update_tab_labels()
        self._auto_close_finished_tabs()

        self.root.after(100, self._poll)

    def _drain(self, line_queue):
        items = []
        while True:
            try:
                items.append(line_queue.get_nowait())
            except queue.Empty:
                break
        return items

    def _poll_incoming_url(self):
        incoming_urls = self._drain(self.url_queue)
        if not incoming_urls:
            return

        tab = self.active_tab()
        if tab is None:
            return

        if tab.is_busy():
            notifier.notify(config.APP_NAME, TAB_BUSY_MESSAGE)
            return

        added_any = False
        for url, browser in incoming_urls:
            if tab.add_incoming_url(url, browser):
                added_any = True

        if added_any:
            notifier.notify(config.APP_NAME, "URL added")

    def _poll_download_trigger(self):
        if not self._drain(self.download_trigger_queue):
            return
        tab = self.active_tab()
        if tab is not None:
            tab.on_download()

    def _poll_check_archive_trigger(self):
        if not self._drain(self.check_archive_trigger_queue):
            return
        tab = self.active_tab()
        if tab is None:
            return
        if tab.is_busy():
            notifier.notify(config.APP_NAME, TAB_BUSY_MESSAGE)
            return
        tab.check_archive_on_last_pasted()
