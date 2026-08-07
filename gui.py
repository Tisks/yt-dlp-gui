import queue
import tkinter as tk

import config
import download_tab
import notifier
import url_server


class DownloaderApp:
    def __init__(self):
        self.url_queue = queue.Queue()
        self.download_trigger_queue = queue.Queue()
        self.check_archive_trigger_queue = queue.Queue()

        self.root = tk.Tk()
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_GEOMETRY)

        self.tab = download_tab.DownloadTab(self, self.root)
        self.tab.frame.pack(expand=True)

        self._start_url_server()
        self._poll_bridge_queues()

    def _start_url_server(self):
        try:
            url_server.start_server(self.url_queue, self.download_trigger_queue, self.check_archive_trigger_queue)
        except OSError as exc:
            self.tab.error_text.config(state="normal")
            self.tab.error_text.insert("end", f"URL receiver not started: {exc}\n")
            self.tab.error_text.config(state="disabled")

    def _poll_bridge_queues(self):
        self._poll_incoming_url()
        self._poll_download_trigger()
        self._poll_check_archive_trigger()

        self.root.after(100, self._poll_bridge_queues)

    def _poll_incoming_url(self):
        try:
            url = self.url_queue.get_nowait()
        except queue.Empty:
            return

        existing_urls = {row.entry.get().strip() for row in self.tab.url_rows}
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
        empty_row = next((row for row in self.tab.url_rows if not row.entry.get().strip()), None)
        target_row = empty_row if empty_row is not None else self.tab._add_url_row()

        target_row.entry.delete(0, "end")
        target_row.entry.insert(0, url)
        self.tab.last_pasted_row = target_row

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
            self.tab.on_download()

    def _poll_check_archive_trigger(self):
        triggered = False
        while True:
            try:
                self.check_archive_trigger_queue.get_nowait()
            except queue.Empty:
                break
            triggered = True

        if triggered and self.tab.last_pasted_row in self.tab.url_rows:
            self.tab.last_pasted_row.archive_var.set(True)

    def run(self):
        self.root.mainloop()
