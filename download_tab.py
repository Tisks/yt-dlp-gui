"""One download batch: its URL rows, its yt-dlp processes and its own output.

Each tab owns everything that used to be per-batch state on the app. Keeping
processes and logs per tab is what makes concurrent batches readable -- two
batches running at once would otherwise interleave their yt-dlp output into a
single box with no way to tell the lines apart.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from collections import namedtuple

import config
import downloader
from core import batch as batch_state
from core import paths
import notifier
import platform_support

MAX_VISIBLE_ROWS = 2
PLAYLIST_ITEMS_PLACEHOLDER = "e.g. 1,3,7-10"
PLACEHOLDER_FG = "gray"
TICK_OK = "✓"
TICK_FAIL = "✗"
TICK_OK_FG = "#2ecc40"
TICK_FAIL_FG = "red"

# Shown when something tries to change a batch that is already downloading.
TAB_BUSY_MESSAGE = "Please change the tab the download has already started"

_URLRow = namedtuple(
    "_URLRow",
    "entry archive_var archive_check frame url_var playlist_items_var playlist_items_entry "
    "tick_label is_first cookies_browser_var remove_button",
)


class DownloadTab:
    """A single batch. `frame` is the page added to the app's notebook."""

    def __init__(self, app, notebook):
        self.app = app
        self.root = app.root

        self.stdout_queue = queue.Queue()
        self.stderr_queue = queue.Queue()
        self.done_queue = queue.Queue()

        self.url_rows = []
        self.last_pasted_row = None
        self.pending_downloads = 0
        self.active_processes = []
        self.process_rows = {}
        self.suppress_output = False
        self.has_run = False
        self.had_failure = False
        self.custom_name = None

        self.frame = ttk.Frame(notebook, padding=(0, 8, 0, 0))
        self._build_widgets()

    # ------------------------------------------------------------------ state

    def is_busy(self):
        return self.pending_downloads > 0

    def is_finished(self):
        """Has run at least one download and has nothing in flight."""
        return self.has_run and self.pending_downloads == 0

    def status(self):
        return batch_state.status(self.pending_downloads, self.has_run, self.had_failure)

    def has_any_url(self):
        return any(row.entry.get().strip() for row in self.url_rows)

    def _forget_result_when_emptied(self):
        """Drop the ✓/✗ once the user has cleared every URL out of the tab.

        Clearing `has_run` rather than only hiding the glyph matters: otherwise
        typing a fresh URL would bring back a mark describing a batch that never
        ran on it.

        The ● is deliberately not clearable. It is driven by pending_downloads,
        which also decides whether the tab may be closed -- a tab must never
        read as idle while yt-dlp is still writing files, or it could be closed
        out from under running processes. In practice this branch cannot be
        reached mid-download anyway, since every row input is disabled then.
        """
        if batch_state.should_forget_result(
            self.pending_downloads, self.has_run, self.has_any_url()
        ):
            self.has_run = False
            self.had_failure = False

    # --------------------------------------------------------------- widgets

    def _build_widgets(self):
        container = self.frame

        local_header = ttk.Frame(container)
        local_header.pack(pady=(0, 4), fill="x")

        ttk.Label(local_header, text="Local path").pack(side="left")

        # A bare glyph rather than a drawn button: this only shows/hides the
        # field, so it should not read as heavily as the round +/- row buttons.
        self.local_path_toggle = tk.Label(
            local_header, text="+", font=("", 13, "bold"), cursor=platform_support.CURSOR_CLICKABLE
        )
        self.local_path_toggle.pack(side="left", padx=(6, 0))
        self.local_path_toggle.bind("<Button-1>", lambda event: self.toggle_local_path())

        self.local_path_var = tk.StringVar(value="")
        # Deliberately narrower than the tab's other content: at 52 the field
        # became the widest thing in the tab, so expanding it visibly widened
        # the whole notebook. Left with margin because Windows renders entries
        # and text boxes in different fonts.
        self.local_path_entry = ttk.Entry(
            container, textvariable=self.local_path_var, width=46, cursor=platform_support.CURSOR_TEXT
        )
        self.local_path_expanded = False  # starts collapsed; entry is not packed yet

        # Packed unconditionally so an error stays visible after collapsing --
        # pack order then floats it up under the "Local path" label by itself.
        self.local_path_message = ttk.Label(container, text="", foreground="red")
        self.local_path_message.pack(pady=(0, 4), fill="x", anchor="w")

        self.local_path_var.trace_add(
            "write", lambda *_args: self.local_path_message.config(text="")
        )

        url_header = ttk.Frame(container)
        url_header.pack(pady=(0, 4), fill="x")

        ttk.Label(url_header, text="URL").pack(side="left")

        add_row_button = self._make_round_button(url_header, "+")
        add_row_button.pack(side="left", padx=(6, 0))
        add_row_button.bind("<Button-1>", lambda event: self._on_add_row_clicked())

        rows_outer = ttk.Frame(container)
        rows_outer.pack(pady=(0, 4), fill="x")

        self.rows_canvas = tk.Canvas(rows_outer, highlightthickness=0)
        self.rows_scrollbar = ttk.Scrollbar(rows_outer, orient="vertical", command=self.rows_canvas.yview)
        self.rows_canvas.configure(yscrollcommand=self.rows_scrollbar.set)
        # No fill/expand: tk.Canvas paints an opaque background while the ttk
        # widgets around it let the notebook pane show through, so any canvas
        # wider than its rows renders as a visible block next to the checkbox.
        # _update_rows_layout keeps its width pinned to the row content instead.
        self.rows_canvas.pack(side="left")

        self.rows_frame = ttk.Frame(self.rows_canvas)
        self.rows_canvas_window = self.rows_canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")

        self.rows_frame.bind("<Configure>", lambda event: self._update_rows_layout())
        self.rows_canvas.bind("<Enter>", self._on_rows_area_enter)
        self.rows_canvas.bind("<Leave>", self._on_rows_area_leave)

        self._add_url_row()

        self.output_text = scrolledtext.ScrolledText(container, width=56, height=9, state="disabled", wrap="word")
        self.output_text.pack(pady=(0, 6))

        ttk.Button(
            container, text="Clean", command=self.on_clean_output, cursor=platform_support.CURSOR_CLICKABLE
        ).pack(pady=(0, 4))

        self.error_text = scrolledtext.ScrolledText(
            container, width=56, height=5, state="disabled", wrap="word", foreground="red"
        )
        self.error_text.pack(pady=(0, 6))

        ttk.Button(
            container, text="Clean", command=self.on_clean_error, cursor=platform_support.CURSOR_CLICKABLE
        ).pack(pady=(0, 4))

        self.message_label = ttk.Label(container, text="", foreground="red")
        self.message_label.pack(pady=(0, 8))

        button_row = ttk.Frame(container)
        button_row.pack()

        self.cancel_button = ttk.Button(
            button_row,
            text="Cancel",
            command=self.on_cancel,
            state="disabled",
            cursor=platform_support.CURSOR_DISABLED,
        )
        self.cancel_button.pack(side="left", padx=(0, 6))

        self.download_button = ttk.Button(
            button_row, text="Download", command=self.on_download, cursor=platform_support.CURSOR_CLICKABLE
        )
        self.download_button.pack(side="left")

    def _make_round_button(self, parent, symbol):
        button = tk.Canvas(parent, width=22, height=22, highlightthickness=0, bg=self.app.frame_bg)
        button.create_oval(1, 1, 21, 21, fill="#565759", outline="black", width=1)
        button.create_text(11, 11, text=symbol, fill="white", font=("", 13, "bold"), anchor="center")
        button.config(cursor=platform_support.CURSOR_CLICKABLE)
        return button

    def _set_button_enabled(self, button, enabled):
        button.config(
            state="normal" if enabled else "disabled",
            cursor=platform_support.CURSOR_CLICKABLE if enabled else platform_support.CURSOR_DISABLED,
        )

    def toggle_local_path(self):
        """Show/hide the local path field. The typed value is kept either way."""
        if self.local_path_expanded:
            self.local_path_entry.pack_forget()
            self.local_path_toggle.config(text="+")
        else:
            self.local_path_entry.pack(before=self.local_path_message, pady=(0, 4), anchor="w")
            self.local_path_toggle.config(text="_")
        self.local_path_expanded = not self.local_path_expanded

    def _set_row_inputs_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        text_cursor = platform_support.CURSOR_TEXT if enabled else platform_support.CURSOR_DISABLED
        clickable_cursor = platform_support.CURSOR_CLICKABLE if enabled else platform_support.CURSOR_DISABLED
        self.local_path_entry.config(state=state, cursor=text_cursor)
        for row in self.url_rows:
            row.entry.config(state=state, cursor=text_cursor)
            row.playlist_items_entry.config(state=state, cursor=text_cursor)
            row.archive_check.config(state=state, cursor=clickable_cursor)
            if row.remove_button is not None:
                row.remove_button.config(cursor=clickable_cursor)

    def _append_text(self, text_widget, message):
        text_widget.config(state="normal")
        text_widget.insert("end", message)
        text_widget.see("end")
        text_widget.config(state="disabled")

    def _clear_text(self, text_widget):
        text_widget.config(state="normal")
        text_widget.delete("1.0", "end")
        text_widget.config(state="disabled")

    # ------------------------------------------------------------------ rows

    def _on_add_row_clicked(self):
        if self.is_busy():
            notifier.notify(config.APP_NAME, TAB_BUSY_MESSAGE)
            return
        row = self._add_url_row()
        row.entry.focus_set()

    def _on_remove_row_clicked(self, row):
        if self.is_busy():
            notifier.notify(config.APP_NAME, TAB_BUSY_MESSAGE)
            return
        self._remove_url_row(row)

    def _add_url_row(self, initial_url="", cookies_browser=None):
        is_first_row = not self.url_rows

        row_frame = ttk.Frame(self.rows_frame)
        row_frame.pack(pady=(0, 6), fill="x")

        # ttk rather than tk: a tk.Label paints an opaque background that does
        # not match the notebook pane, showing as a block beside each row.
        # ttk.Label still honours `foreground`, which is all the ✓/✗ needs.
        tick_label = ttk.Label(row_frame, text="", width=2, font=("", 12, "bold"))
        tick_label.pack(side="left", padx=(0, 4))

        url_var = tk.StringVar(value=initial_url)
        entry = ttk.Entry(row_frame, width=24, textvariable=url_var, cursor=platform_support.CURSOR_TEXT)
        entry.pack(side="left")

        entry_menu = tk.Menu(entry, tearoff=0)
        entry_menu.add_command(label="Cut", command=lambda: entry.event_generate("<<Cut>>"))
        entry_menu.add_command(label="Copy", command=lambda: entry.event_generate("<<Copy>>"))
        entry_menu.add_command(label="Paste", command=lambda: entry.event_generate("<<Paste>>"))
        entry_menu.add_separator()
        entry_menu.add_command(label="Select All", command=lambda: entry.select_range(0, "end"))

        def show_entry_menu(event):
            entry.focus_set()
            entry_menu.tk_popup(event.x_root, event.y_root)

        entry.bind("<Button-2>", show_entry_menu)
        entry.bind("<Button-3>", show_entry_menu)

        playlist_items_var = tk.StringVar(value=PLAYLIST_ITEMS_PLACEHOLDER)
        playlist_items_entry = ttk.Entry(
            row_frame, width=9, textvariable=playlist_items_var, cursor=platform_support.CURSOR_TEXT
        )
        playlist_items_entry.pack(side="left", padx=(6, 0))
        default_fg = playlist_items_entry.cget("foreground")
        playlist_items_entry.config(foreground=PLACEHOLDER_FG)

        def on_playlist_items_focus_in(event):
            if playlist_items_var.get() == PLAYLIST_ITEMS_PLACEHOLDER:
                playlist_items_entry.delete(0, "end")
                playlist_items_entry.config(foreground=default_fg)

        def on_playlist_items_focus_out(event):
            if not playlist_items_var.get().strip():
                playlist_items_entry.insert(0, PLAYLIST_ITEMS_PLACEHOLDER)
                playlist_items_entry.config(foreground=PLACEHOLDER_FG)

        playlist_items_entry.bind("<FocusIn>", on_playlist_items_focus_in)
        playlist_items_entry.bind("<FocusOut>", on_playlist_items_focus_out)

        archive_var = tk.BooleanVar(value=False)
        archive_check = ttk.Checkbutton(row_frame, variable=archive_var, cursor=platform_support.CURSOR_CLICKABLE)
        archive_check.pack(side="left", padx=(6, 0))

        remove_button = None
        if not is_first_row:
            remove_button = self._make_round_button(row_frame, "-")
            remove_button.pack(side="left", padx=(6, 0))

        # Empty means the row follows the app-wide dropdown; the extension fills
        # this in so a URL sent from Firefox reads Firefox's cookies regardless.
        cookies_browser_var = tk.StringVar(value=cookies_browser or "")

        row = _URLRow(
            entry,
            archive_var,
            archive_check,
            row_frame,
            url_var,
            playlist_items_var,
            playlist_items_entry,
            tick_label,
            is_first_row,
            cookies_browser_var,
            remove_button,
        )
        self.url_rows.append(row)

        if remove_button is not None:
            remove_button.bind("<Button-1>", lambda event, row=row: self._on_remove_row_clicked(row))

        url_var.trace_add("write", lambda *_args, row=row: self._on_row_url_edited(row))
        if not is_first_row:
            url_var.trace_add("write", lambda *_args, row=row: self._on_row_url_changed(row))

        return row

    def _update_rows_layout(self):
        self.root.update_idletasks()
        row_count = len(self.url_rows)
        bbox = self.rows_canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0
        content_width = (bbox[2] - bbox[0]) if bbox else 0
        self.rows_canvas.configure(width=content_width)

        if row_count <= MAX_VISIBLE_ROWS:
            self.rows_canvas.configure(height=content_height)
            self.rows_scrollbar.pack_forget()
        else:
            row_height = content_height / row_count
            self.rows_canvas.configure(height=int(row_height * MAX_VISIBLE_ROWS))
            # side="left" keeps it against the canvas: the canvas no longer
            # expands, so a right-packed scrollbar would drift to the far edge.
            self.rows_scrollbar.pack(side="left", fill="y")

        self.rows_canvas.configure(scrollregion=bbox)

    def _on_rows_mousewheel(self, event):
        self.rows_canvas.yview_scroll(platform_support.normalize_wheel_delta(event), "units")

    def _on_rows_area_enter(self, event):
        self.root.bind_all("<MouseWheel>", self._on_rows_mousewheel)

    def _on_rows_area_leave(self, event):
        self.root.unbind_all("<MouseWheel>")

    def _on_row_url_edited(self, row):
        row.tick_label.config(text="")

    def _on_row_url_changed(self, row):
        if row.entry.get().strip():
            return
        self.root.after_idle(lambda: self._remove_url_row(row))

    def _remove_url_row(self, row):
        if row not in self.url_rows:
            return
        self.url_rows.remove(row)
        row.frame.destroy()
        self._update_rows_layout()

    # -------------------------------------------------------- incoming URLs

    def add_incoming_url(self, url, browser):
        """Place a URL sent by the browser extension. Returns True if added."""
        existing_urls = {row.entry.get().strip() for row in self.url_rows}
        if url in existing_urls:
            notifier.notify(config.APP_NAME, "URL already on queue")
            return False

        empty_row = next((row for row in self.url_rows if not row.entry.get().strip()), None)
        if empty_row is not None:
            empty_row.entry.delete(0, "end")
            empty_row.entry.insert(0, url)
            empty_row.cookies_browser_var.set(browser)
            self.last_pasted_row = empty_row
        else:
            self.last_pasted_row = self._add_url_row(url, cookies_browser=browser)

        return True

    def check_archive_on_last_pasted(self):
        if self.last_pasted_row in self.url_rows:
            self.last_pasted_row.archive_var.set(True)

    # ------------------------------------------------------------- download

    def _row_cookies_browser(self, row):
        """Where to read cookies for this row.

        Rows sent by the extension carry the browser they came from; rows typed
        by hand follow the dropdown, read now so it tracks the current choice.
        """
        return row.cookies_browser_var.get() or self.app.cookies_browser_var.get()

    def _get_playlist_items(self, row):
        value = row.playlist_items_var.get().strip()
        if value == PLAYLIST_ITEMS_PLACEHOLDER:
            return ""
        return value

    def _collect_url_entries(self):
        entries = []
        for row in self.url_rows:
            url = row.entry.get().strip()
            if not url:
                continue
            entries.append(
                (row, url, row.archive_var.get(), self._get_playlist_items(row), self._row_cookies_browser(row))
            )
        return entries

    def _path_error(self, path):
        """Why `path` is unusable as a download folder, or None if it is fine."""
        return paths.path_error(path)

    def resolve_download_path(self):
        """The folder this batch downloads into, or None if validation failed.

        The choice itself is in core.paths; all this adds is putting any
        complaint on the warning label belonging to the field it came from.
        """
        path, field, message = paths.resolve_download_path(
            self.local_path_var.get(), self.app.path_var.get()
        )
        if path is None:
            if field == paths.LOCAL:
                self._fail_local_path(message)
            else:
                self._fail_path_validation(message)
        return path

    def _fail_path_validation(self, message):
        notifier.notify(config.APP_NAME, message)
        self.message_label.config(text=message)

    def _fail_local_path(self, message):
        notifier.notify(config.APP_NAME, message)
        self.local_path_message.config(text=message)

    def on_download(self):
        if self.is_busy():
            notifier.notify(config.APP_NAME, "Download in progress")
            return

        entries = self._collect_url_entries()
        if not entries:
            self.message_label.config(text="Please input something")
            return

        path = self.resolve_download_path()
        if path is None:
            return

        self.message_label.config(text="")
        self.local_path_message.config(text="")
        self.suppress_output = False
        self._clear_text(self.output_text)
        self._clear_text(self.error_text)
        for row, _url, _is_archive, _playlist_items, _cookies_browser in entries:
            row.tick_label.config(text="")

        self._set_button_enabled(self.download_button, False)

        self.pending_downloads = 0
        self.active_processes = []
        cookies_file = self.app.cookies_file_var.get()
        for (is_archive, playlist_items, cookies_browser), rows, group_urls in (
            batch_state.group_downloads(entries)
        ):
            if is_archive:
                command = downloader.build_channel_command(
                    group_urls, path, playlist_items, cookies_browser, cookies_file
                )
            else:
                command = downloader.build_single_command(
                    group_urls, path, playlist_items, cookies_browser, cookies_file
                )

            try:
                proc = downloader.start_download(command, self.stdout_queue, self.stderr_queue, self.done_queue)
                self.active_processes.append(proc)
                self.process_rows[proc] = rows
                self.pending_downloads += 1
            except OSError as exc:
                self._append_text(self.error_text, f"Failed to start yt-dlp: {exc}\n")

        if self.pending_downloads == 0:
            self._set_button_enabled(self.download_button, True)
        else:
            self.has_run = True
            self.had_failure = False
            self._set_button_enabled(self.cancel_button, True)
            self._set_row_inputs_enabled(False)
            # The path just passed validation, so this is the safest moment to
            # remember it and the browser it was downloaded with.
            self.app.save_settings()
            notifier.notify(config.APP_NAME, "Download started")

    def on_cancel(self):
        if not self.active_processes:
            return

        for proc in self.active_processes:
            downloader.cancel_download(proc)
        self._set_button_enabled(self.cancel_button, False)
        self.suppress_output = True
        self.had_failure = True

        for line_queue in (self.stdout_queue, self.stderr_queue):
            while True:
                try:
                    line_queue.get_nowait()
                except queue.Empty:
                    break

        self._clear_text(self.output_text)
        self._clear_text(self.error_text)
        self._append_text(self.error_text, "Download cancelled\n")

    def cancel_silently(self):
        """Stop this tab's processes without touching widgets (used when closing)."""
        for proc in self.active_processes:
            downloader.cancel_download(proc)
        self.active_processes = []
        self.pending_downloads = 0

    def on_clean_output(self):
        self._clear_text(self.output_text)

    def on_clean_error(self):
        self._clear_text(self.error_text)

    # ----------------------------------------------------------------- poll

    def _drain_queue_into(self, line_queue, text_widget):
        drained_any = False
        while True:
            try:
                line = line_queue.get_nowait()
            except queue.Empty:
                break
            drained_any = True
            if self.suppress_output:
                continue
            self._append_text(text_widget, line)
        return drained_any

    def poll(self):
        self._drain_queue_into(self.stdout_queue, self.output_text)
        got_error_output = self._drain_queue_into(self.stderr_queue, self.error_text)
        if got_error_output:
            self._set_button_enabled(self.download_button, True)

        while True:
            try:
                proc, returncode = self.done_queue.get_nowait()
            except queue.Empty:
                break
            self.pending_downloads = max(0, self.pending_downloads - 1)
            rows = self.process_rows.pop(proc, [])
            succeeded = returncode == 0
            if not succeeded:
                self.had_failure = True
            for row in rows:
                if row in self.url_rows:
                    row.tick_label.config(
                        text=TICK_OK if succeeded else TICK_FAIL,
                        foreground=TICK_OK_FG if succeeded else TICK_FAIL_FG,
                    )

        if self.pending_downloads == 0:
            self._set_button_enabled(self.download_button, True)
            self._set_button_enabled(self.cancel_button, False)
            self._set_row_inputs_enabled(True)
            self.active_processes = []

        self._forget_result_when_emptied()

    def destroy(self):
        self.cancel_silently()
        self.frame.destroy()
