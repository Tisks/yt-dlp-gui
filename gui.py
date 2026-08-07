import queue
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext

import config
import downloader


class DownloaderApp:
    def __init__(self):
        self.stdout_queue = queue.Queue()
        self.stderr_queue = queue.Queue()
        self.done_queue = queue.Queue()

        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_GEOMETRY)

        self._build_widgets()
        self._poll_output_queue()

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

        url_row = ttk.Frame(container)
        url_row.pack(pady=(0, 4))

        self.url_entry = ttk.Entry(url_row, width=32)
        self.url_entry.pack(side="left")

        self.channel_var = tk.BooleanVar(value=False)
        channel_check = ttk.Checkbutton(url_row, text="Channel", variable=self.channel_var)
        channel_check.pack(side="left", padx=(6, 0))

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

    def on_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self.message_label.config(text="Please input something")
            return

        self.message_label.config(text="")
        for text_widget in (self.output_text, self.error_text):
            text_widget.config(state="normal")
            text_widget.delete("1.0", "end")
            text_widget.config(state="disabled")

        if self.channel_var.get():
            command = downloader.build_channel_command(url)
        else:
            command = downloader.build_single_command(url, self.path_var.get())

        self.download_button.config(state="disabled")

        try:
            downloader.start_download(command, self.stdout_queue, self.stderr_queue, self.done_queue)
        except OSError as exc:
            self.error_text.config(state="normal")
            self.error_text.insert("end", f"Failed to start yt-dlp: {exc}\n")
            self.error_text.config(state="disabled")
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
            self.download_button.config(state="normal")

        self.root.after(100, self._poll_output_queue)

    def run(self):
        self.root.mainloop()
