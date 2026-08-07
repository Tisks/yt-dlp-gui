import queue
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from collections import namedtuple

import config
import downloader
import url_server

_URLRow = namedtuple("_URLRow", "entry channel_var frame")


class DownloaderApp:
    def __init__(self):
        self.stdout_queue = queue.Queue()
        self.stderr_queue = queue.Queue()
        self.done_queue = queue.Queue()
        self.url_queue = queue.Queue()

        self.url_rows = []
        self.pending_downloads = 0

        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_GEOMETRY)

        self._build_widgets()
        self._start_url_server()
        self._poll_output_queue()

    def _start_url_server(self):
        try:
            url_server.start_server(self.url_queue)
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

        url_label = ttk.Label(container, text="URL")
        url_label.pack(pady=(0, 4), fill="x", anchor="w")

        self.rows_frame = ttk.Frame(container)
        self.rows_frame.pack(pady=(0, 4), fill="x")

        self._add_url_row()

        self.output_text = scrolledtext.ScrolledText(container, width=42, height=10, state="disabled", wrap="word")
        self.output_text.pack(pady=(0, 4))

        self.error_text = scrolledtext.ScrolledText(
            container, width=42, height=6, state="disabled", wrap="word", foreground="red"
        )
        self.error_text.pack(pady=(0, 4))

        self.message_label = ttk.Label(container, text="", foreground="red")
        self.message_label.pack(pady=(0, 8))

        self.download_button = ttk.Button(container, text="Download", command=self.on_download)
        self.download_button.pack()

    def _add_url_row(self, initial_url=""):
        row_frame = ttk.Frame(self.rows_frame)
        row_frame.pack(pady=(0, 6), fill="x")

        entry = ttk.Entry(row_frame, width=32)
        entry.insert(0, initial_url)
        entry.pack(side="left")

        channel_var = tk.BooleanVar(value=False)
        channel_check = ttk.Checkbutton(row_frame, text="Channel", variable=channel_var)
        channel_check.pack(side="left", padx=(6, 0))

        row = _URLRow(entry, channel_var, row_frame)
        self.url_rows.append(row)
        return row

    def _collect_url_entries(self):
        entries = []
        for row in self.url_rows:
            url = row.entry.get().strip()
            if not url:
                continue
            entries.append((url, row.channel_var.get()))
        return entries

    def on_download(self):
        entries = self._collect_url_entries()
        if not entries:
            self.message_label.config(text="Please input something")
            return

        self.message_label.config(text="")
        for text_widget in (self.output_text, self.error_text):
            text_widget.config(state="normal")
            text_widget.delete("1.0", "end")
            text_widget.config(state="disabled")

        self.download_button.config(state="disabled")

        # yt-dlp accepts more than one URL per invocation, so URLs that share
        # a checkbox state are downloaded together in a single command instead
        # of spawning one process per row.
        groups = {}
        for url, is_channel in entries:
            groups.setdefault(is_channel, []).append(url)

        self.pending_downloads = 0
        for is_channel, urls in groups.items():
            if is_channel:
                command = downloader.build_channel_command(urls)
            else:
                command = downloader.build_single_command(urls, self.path_var.get())

            try:
                downloader.start_download(command, self.stdout_queue, self.stderr_queue, self.done_queue)
                self.pending_downloads += 1
            except OSError as exc:
                self.error_text.config(state="normal")
                self.error_text.insert("end", f"Failed to start yt-dlp: {exc}\n")
                self.error_text.config(state="disabled")

        if self.pending_downloads == 0:
            self.download_button.config(state="normal")

    def _drain_queue_into(self, line_queue, text_widget):
        while True:
            try:
                line = line_queue.get_nowait()
            except queue.Empty:
                break
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

        self._poll_incoming_url()

        self.root.after(100, self._poll_output_queue)

    def _poll_incoming_url(self):
        try:
            url = self.url_queue.get_nowait()
        except queue.Empty:
            return

        # Only the widget's text changes here -- never call lift()/focus_force()
        # or deiconify(), or receiving a URL from Chrome would yank focus away
        # from the browser and pull this window to the front over it.
        last_row = self.url_rows[-1]
        if last_row.entry.get().strip():
            last_row = self._add_url_row()

        last_row.entry.delete(0, "end")
        last_row.entry.insert(0, url)

    def run(self):
        self.root.mainloop()
