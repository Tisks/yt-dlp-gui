import os
import subprocess
import threading

import config
import platform_support


def build_env():
    env = os.environ.copy()
    current = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(config.EXTRA_PATHS + [current])
    return env


def _cookies_flags(cookies_browser=None, cookies_file=None):
    # A user-supplied file is a deliberate override -- it sidesteps browser
    # cookie decryption entirely (see the Windows DPAPI/App-Bound Encryption
    # failures --cookies-from-browser can hit), so it always wins when set.
    if cookies_file:
        return ["--cookies", cookies_file]
    return ["--cookies-from-browser", cookies_browser or config.DEFAULT_COOKIES_BROWSER]


def _shared_flags(cookies_browser=None, cookies_file=None):
    return [
        *_cookies_flags(cookies_browser, cookies_file),
        "--js-runtimes", config.JS_RUNTIME,
        "-f", config.VIDEO_FORMAT,
        "--merge-output-format", config.MERGE_FORMAT,
    ]


def build_channel_command(urls, path, playlist_items="", cookies_browser=None, cookies_file=None):
    archive_file = os.path.join(path, config.CHANNEL_ARCHIVE_FILENAME)
    command = [
        config.YT_DLP_BIN,
        "-P", path,
        *_shared_flags(cookies_browser, cookies_file),
    ]
    if playlist_items:
        command += ["--playlist-items", playlist_items]
    command += [
        "--write-subs",
        "--write-auto-subs",
        "--embed-subs",
        "--write-thumbnail",
        "--embed-thumbnail",
        "--write-info-json",
        "--embed-metadata",
        "--download-archive", archive_file,
        "--continue",
        "--ignore-errors",
        "--concurrent-fragments", config.CHANNEL_CONCURRENT_FRAGMENTS,
        "-o", config.CHANNEL_OUTPUT_TEMPLATE,
    ]
    command += list(urls)
    return command


def build_single_command(urls, path, playlist_items="", cookies_browser=None, cookies_file=None):
    command = [config.YT_DLP_BIN, "-P", path, *_shared_flags(cookies_browser, cookies_file)]
    if playlist_items:
        command += ["--playlist-items", playlist_items]
    command += list(urls)
    return command


def stream_output(pipe, line_queue):
    for line in pipe:
        line_queue.put(line)
    pipe.close()


def _monitor_process(proc, reader_threads, done_queue):
    for reader_thread in reader_threads:
        reader_thread.join()
    proc.wait()
    done_queue.put((proc, proc.returncode))


def start_download(command, stdout_queue, stderr_queue, done_queue):
    proc = subprocess.Popen(
        command,
        env=build_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        **platform_support.subprocess_flags(),
    )

    stdout_thread = threading.Thread(target=stream_output, args=(proc.stdout, stdout_queue), daemon=True)
    stderr_thread = threading.Thread(target=stream_output, args=(proc.stderr, stderr_queue), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    threading.Thread(
        target=_monitor_process, args=(proc, [stdout_thread, stderr_thread], done_queue), daemon=True
    ).start()

    return proc


def cancel_download(proc):
    platform_support.terminate_process_tree(proc)
