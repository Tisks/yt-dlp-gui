import queue
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from collections import namedtuple

import config
import downloader
import notifier
import url_server

MAX_VISIBLE_ROWS = 3
PLAYLIST_ITEMS_PLACEHOLDER = "e.g. 1,3,7-10"

_URLRow = namedtuple("_URLRow", "entry archive_var frame url_var playlist_items_var")


class DownloaderApp:
    def __init__(self):
        self.stdout_queue = queue.Queue()
        self.stderr_queue = queue.Queue()
        self.done_queue = queue.Queue()
        self.url_queue = queue.Queue()
        self.download_trigger_queue = queue.Queue()
        self.check_archive_trigger_queue = queue.Queue()

        self.url_rows = []
        self.last_pasted_row = None
        self.pending_downloads = 0
        self.active_processes = []
        self.suppress_output = False

        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_GEOMETRY)

        self._build_widgets()
        self._start_url_server()
        self._poll_output_queue()

    def _start_url_server(self):
        try:
            url_server.start_server(self.url_queue, self.download_trigger_queue, self.check_archive_trigger_queue)
        except OSError as exc:
            self.error_text.config(state="normal")
            self.error_text.insert("end", f"URL receiver not started: {exc}\n")
            self.error_text.config(state="disabled")

    def _build_widgets(self):
        container = ttk.Frame(self.root, padding=20)
        container.pack(expand=True)

        path_label = ttk.Label(container, text="Path")
        path_label.pack(pady=(0, 4), fill="x", anchor="w")

        self.path_var = tk.StringVar(value=config.DEFAULT_PATH)
        path_combo = ttk.Combobox(
            container,
            textvariable=self.path_var,
            values=config.PATH_OPTIONS,
            state="readonly",
            width=37,
        )
        path_combo.pack(pady=(0, 4))

        url_header = ttk.Frame(container)
        url_header.pack(pady=(0, 4), fill="x")

        url_label = ttk.Label(url_header, text="URL")
        url_label.pack(side="left")

        frame_bg = ttk.Style().lookup("TFrame", "background") or "systemWindowBackgroundColor"

        add_row_button = tk.Canvas(
            url_header, width=22, height=22, highlightthickness=0, bg=frame_bg
        )
        add_row_button.pack(side="left", padx=(6, 0))
        add_row_button.create_oval(1, 1, 21, 21, fill="#565759", outline="black", width=1)
        add_row_button.create_text(11, 11, text="+", fill="white", font=("", 13, "bold"), anchor="center")
        add_row_button.config(cursor="pointinghand")
        add_row_button.bind("<Button-1>", lambda event: self._on_add_row_clicked())

        rows_outer = ttk.Frame(container)
        rows_outer.pack(pady=(0, 4), fill="x")

        self.rows_canvas = tk.Canvas(rows_outer, highlightthickness=0)
        self.rows_scrollbar = ttk.Scrollbar(rows_outer, orient="vertical", command=self.rows_canvas.yview)
        self.rows_canvas.configure(yscrollcommand=self.rows_scrollbar.set)
        self.rows_canvas.pack(side="left", fill="both", expand=True)

        self.rows_frame = ttk.Frame(self.rows_canvas)
        self.rows_canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")

        self.rows_frame.bind("<Configure>", lambda event: self._update_rows_layout())

        self._add_url_row()

        self.output_text = scrolledtext.ScrolledText(container, width=42, height=10, state="disabled", wrap="word")
        self.output_text.pack(pady=(0, 4))

        self.error_text = scrolledtext.ScrolledText(
            container, width=42, height=6, state="disabled", wrap="word", foreground="red"
        )
        self.error_text.pack(pady=(0, 4))

        self.message_label = ttk.Label(container, text="", foreground="red")
        self.message_label.pack(pady=(0, 8))

        button_row = ttk.Frame(container)
        button_row.pack()

        self.cancel_button = ttk.Button(button_row, text="Cancel", command=self.on_cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 6))

        self.download_button = ttk.Button(button_row, text="Download", command=self.on_download)
        self.download_button.pack(side="left")

    def _on_add_row_clicked(self):
        row = self._add_url_row()
        row.entry.focus_set()

    def _add_url_row(self, initial_url=""):
        is_first_row = not self.url_rows

        row_frame = ttk.Frame(self.rows_frame)
        row_frame.pack(pady=(0, 6), fill="x")

        url_var = tk.StringVar(value=initial_url)
        entry = ttk.Entry(row_frame, width=32, textvariable=url_var)
        entry.pack(side="left")

        playlist_items_var = tk.StringVar(value=PLAYLIST_ITEMS_PLACEHOLDER)
        playlist_items_entry = ttk.Entry(row_frame, width=9, textvariable=playlist_items_var)
        playlist_items_entry.pack(side="left", padx=(6, 0))
        default_fg = playlist_items_entry.cget("foreground")
        placeholder_fg = "gray"
        playlist_items_entry.config(foreground=placeholder_fg)

        def on_playlist_items_focus_in(event):
            if playlist_items_var.get() == PLAYLIST_ITEMS_PLACEHOLDER:
                playlist_items_entry.delete(0, "end")
                playlist_items_entry.config(foreground=default_fg)

        def on_playlist_items_focus_out(event):
            if not playlist_items_var.get().strip():
                playlist_items_entry.insert(0, PLAYLIST_ITEMS_PLACEHOLDER)
                playlist_items_entry.config(foreground=placeholder_fg)

        playlist_items_entry.bind("<FocusIn>", on_playlist_items_focus_in)
        playlist_items_entry.bind("<FocusOut>", on_playlist_items_focus_out)

        archive_var = tk.BooleanVar(value=False)
        archive_check = ttk.Checkbutton(row_frame, text="Archive mode", variable=archive_var)
        archive_check.pack(side="left", padx=(6, 0))

        row = _URLRow(entry, archive_var, row_frame, url_var, playlist_items_var)
        self.url_rows.append(row)

        # The first row is the app's permanent URL field; only rows added on
        # top of it should disappear when the user clears them back out.
        if not is_first_row:
            url_var.trace_add("write", lambda *_args, row=row: self._on_row_url_changed(row))

        return row

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

    def _update_rows_layout(self):
        self.root.update_idletasks()
        row_count = len(self.url_rows)
        bbox = self.rows_canvas.bbox("all")
        content_height = (bbox[3] - bbox[1]) if bbox else 0

        if row_count <= MAX_VISIBLE_ROWS:
            self.rows_canvas.configure(height=content_height)
            self.rows_scrollbar.pack_forget()
        else:
            row_height = content_height / row_count
            self.rows_canvas.configure(height=int(row_height * MAX_VISIBLE_ROWS))
            self.rows_scrollbar.pack(side="right", fill="y")

        self.rows_canvas.configure(scrollregion=bbox)

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
            entries.append((url, row.archive_var.get(), self._get_playlist_items(row)))
        return entries

    def on_download(self):
        entries = self._collect_url_entries()
        if not entries:
            self.message_label.config(text="Please input something")
            return

        self.message_label.config(text="")
        self.suppress_output = False
        for text_widget in (self.output_text, self.error_text):
            text_widget.config(state="normal")
            text_widget.delete("1.0", "end")
            text_widget.config(state="disabled")

        self.download_button.config(state="disabled")

        # yt-dlp accepts more than one URL per invocation, so URLs that share
        # the same archive-mode/playlist-items settings are downloaded
        # together in a single command instead of spawning one process per row.
        groups = {}
        for url, is_archive, playlist_items in entries:
            groups.setdefault((is_archive, playlist_items), []).append(url)

        self.pending_downloads = 0
        self.active_processes = []
        for (is_archive, playlist_items), urls in groups.items():
            if is_archive:
                command = downloader.build_channel_command(urls, playlist_items)
            else:
                command = downloader.build_single_command(urls, self.path_var.get(), playlist_items)

            try:
                proc = downloader.start_download(command, self.stdout_queue, self.stderr_queue, self.done_queue)
                self.active_processes.append(proc)
                self.pending_downloads += 1
            except OSError as exc:
                self.error_text.config(state="normal")
                self.error_text.insert("end", f"Failed to start yt-dlp: {exc}\n")
                self.error_text.config(state="disabled")

        if self.pending_downloads == 0:
            self.download_button.config(state="normal")
        else:
            self.cancel_button.config(state="normal")
            notifier.notify("yt-dlp-gui", "Download started")

    def on_cancel(self):
        if not self.active_processes:
            return

        for proc in self.active_processes:
            downloader.cancel_download(proc)
        self.cancel_button.config(state="disabled")
        self.suppress_output = True

        for line_queue in (self.stdout_queue, self.stderr_queue):
            while True:
                try:
                    line_queue.get_nowait()
                except queue.Empty:
                    break

        self.output_text.config(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.config(state="disabled")

        self.error_text.config(state="normal")
        self.error_text.delete("1.0", "end")
        self.error_text.insert("end", "Download cancelled\n")
        self.error_text.config(state="disabled")

    def _drain_queue_into(self, line_queue, text_widget):
        while True:
            try:
                line = line_queue.get_nowait()
            except queue.Empty:
                break
            if self.suppress_output:
                continue
            text_widget.config(state="normal")
            text_widget.insert("end", line)
            text_widget.see("end")
            text_widget.config(state="disabled")

    def _poll_output_queue(self):
        self._drain_queue_into(self.stdout_queue, self.output_text)
        self._drain_queue_into(self.stderr_queue, self.error_text)

        while True:
            try:
                self.done_queue.get_nowait()
            except queue.Empty:
                break
            self.pending_downloads = max(0, self.pending_downloads - 1)

        if self.pending_downloads == 0:
            self.download_button.config(state="normal")
            self.cancel_button.config(state="disabled")
            self.active_processes = []

        self._poll_incoming_url()
        self._poll_download_trigger()
        self._poll_check_archive_trigger()

        self.root.after(100, self._poll_output_queue)

    def _poll_incoming_url(self):
        try:
            url = self.url_queue.get_nowait()
        except queue.Empty:
            return

        existing_urls = {row.entry.get().strip() for row in self.url_rows}
        if url in existing_urls:
            notifier.notify("yt-dlp-gui", "URL already on queue")
            return

        # Only the widget's text changes here -- never call lift()/focus_force()
        # or deiconify(), or receiving a URL from Chrome would yank focus away
        # from the browser and pull this window to the front over it.
        #
        # Fill the first empty row top-to-bottom rather than always the last
        # one: clearing an earlier row while later ones are still filled must
        # reclaim that gap instead of leaving pastes to keep piling up at the
        # bottom in reverse order.
        empty_row = next((row for row in self.url_rows if not row.entry.get().strip()), None)
        target_row = empty_row if empty_row is not None else self._add_url_row()

        target_row.entry.delete(0, "end")
        target_row.entry.insert(0, url)
        self.last_pasted_row = target_row

        # Reaching this point means url_server actually queued the URL, so the
        # notification confirms a real paste rather than firing on every
        # shortcut press regardless of whether it succeeded.
        notifier.notify("yt-dlp-gui", "URL added")

    def _poll_download_trigger(self):
        triggered = False
        while True:
            try:
                self.download_trigger_queue.get_nowait()
            except queue.Empty:
                break
            triggered = True

        if triggered:
            self.on_download()

    def _poll_check_archive_trigger(self):
        triggered = False
        while True:
            try:
                self.check_archive_trigger_queue.get_nowait()
            except queue.Empty:
                break
            triggered = True

        if triggered and self.last_pasted_row in self.url_rows:
            self.last_pasted_row.archive_var.set(True)

    def run(self):
        self.root.mainloop()
