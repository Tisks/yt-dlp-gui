import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext

EXTRA_PATHS = ["/usr/local/bin", "/opt/homebrew/bin"]

COOKIES_BROWSER = "chrome"
JS_RUNTIME = "deno"
VIDEO_FORMAT = "bv*+ba/b"
MERGE_FORMAT = "mkv"

PATH_OPTIONS = ["/Volumes/Elements/downloads", "/Users/user/Downloads"]
DEFAULT_PATH = PATH_OPTIONS[0]

CHANNEL_DOWNLOAD_PATH = "/Volumes/Elements/youtube"
CHANNEL_ARCHIVE_FILE = f"{CHANNEL_DOWNLOAD_PATH}/archive.txt"
CHANNEL_OUTPUT_TEMPLATE = "%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s"
CHANNEL_CONCURRENT_FRAGMENTS = "8"

WINDOW_TITLE = "YT-DLP-GUI"
WINDOW_GEOMETRY = "460x420"

stdout_queue = queue.Queue()
stderr_queue = queue.Queue()
done_queue = queue.Queue()


def build_env():
    env = os.environ.copy()
    current = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(EXTRA_PATHS + [current])
    return env


def build_channel_command(url):
    return [
        "yt-dlp",
        "-P", CHANNEL_DOWNLOAD_PATH,
        "--cookies-from-browser", COOKIES_BROWSER,
        "--js-runtimes", JS_RUNTIME,
        "-f", VIDEO_FORMAT,
        "--merge-output-format", MERGE_FORMAT,
        "--write-subs",
        "--write-auto-subs",
        "--embed-subs",
        "--write-thumbnail",
        "--embed-thumbnail",
        "--write-info-json",
        "--embed-metadata",
        "--download-archive", CHANNEL_ARCHIVE_FILE,
        "--continue",
        "--ignore-errors",
        "--concurrent-fragments", CHANNEL_CONCURRENT_FRAGMENTS,
        "-o", CHANNEL_OUTPUT_TEMPLATE,
        url,
    ]


def build_single_command(url, path):
    return [
        "yt-dlp",
        "-P", path,
        "--cookies-from-browser", COOKIES_BROWSER,
        "--js-runtimes", JS_RUNTIME,
        "-f", VIDEO_FORMAT,
        "--merge-output-format", MERGE_FORMAT,
        url,
    ]


def stream_output(pipe, line_queue):
    for line in pipe:
        line_queue.put(line)
    pipe.close()


def _monitor_process(proc, reader_threads):
    for reader_thread in reader_threads:
        reader_thread.join()
    proc.wait()
    done_queue.put(proc.returncode)


def on_download():
    url = url_entry.get().strip()
    if not url:
        message_label.config(text="Please input something")
        return

    message_label.config(text="")
    output_text.config(state="normal")
    output_text.delete("1.0", "end")
    output_text.config(state="disabled")
    error_text.config(state="normal")
    error_text.delete("1.0", "end")
    error_text.config(state="disabled")

    if channel_var.get():
        command = build_channel_command(url)
    else:
        command = build_single_command(url, path_var.get())

    download_button.config(state="disabled")

    try:
        proc = subprocess.Popen(
            command,
            env=build_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid,
        )
    except OSError as exc:
        error_text.config(state="normal")
        error_text.insert("end", f"Failed to start yt-dlp: {exc}\n")
        error_text.config(state="disabled")
        download_button.config(state="normal")
        return

    stdout_thread = threading.Thread(target=stream_output, args=(proc.stdout, stdout_queue), daemon=True)
    stderr_thread = threading.Thread(target=stream_output, args=(proc.stderr, stderr_queue), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    threading.Thread(target=_monitor_process, args=(proc, [stdout_thread, stderr_thread]), daemon=True).start()


def _drain_queue_into(line_queue, text_widget):
    while True:
        try:
            line = line_queue.get_nowait()
        except queue.Empty:
            break
        text_widget.config(state="normal")
        text_widget.insert("end", line)
        text_widget.see("end")
        text_widget.config(state="disabled")


def poll_output_queue():
    _drain_queue_into(stdout_queue, output_text)
    _drain_queue_into(stderr_queue, error_text)

    while True:
        try:
            done_queue.get_nowait()
        except queue.Empty:
            break
        download_button.config(state="normal")

    root.after(100, poll_output_queue)


root = tk.Tk()
root.title(WINDOW_TITLE)
root.geometry(WINDOW_GEOMETRY)

container = ttk.Frame(root, padding=20)
container.pack(expand=True)

path_label = ttk.Label(container, text="Path")
path_label.pack(pady=(0, 4), fill="x", anchor="w")

path_var = tk.StringVar(value=DEFAULT_PATH)
path_combo = ttk.Combobox(container, textvariable=path_var, values=PATH_OPTIONS, state="readonly", width=37)
path_combo.pack(pady=(0, 4))

url_label = ttk.Label(container, text="URL")
url_label.pack(pady=(0, 4), fill="x", anchor="w")

url_row = ttk.Frame(container)
url_row.pack(pady=(0, 4))

url_entry = ttk.Entry(url_row, width=32)
url_entry.pack(side="left")

channel_var = tk.BooleanVar(value=False)
channel_check = ttk.Checkbutton(url_row, text="Channel", variable=channel_var)
channel_check.pack(side="left", padx=(6, 0))

output_text = scrolledtext.ScrolledText(container, width=42, height=10, state="disabled", wrap="word")
output_text.pack(pady=(0, 4))

error_text = scrolledtext.ScrolledText(container, width=42, height=6, state="disabled", wrap="word", foreground="red")
error_text.pack(pady=(0, 4))

message_label = ttk.Label(container, text="", foreground="red")
message_label.pack(pady=(0, 8))

download_button = ttk.Button(container, text="Download", command=on_download)
download_button.pack()

poll_output_queue()
root.mainloop()
