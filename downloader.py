import os
import subprocess
import threading

import config


def build_env():
    env = os.environ.copy()
    current = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(config.EXTRA_PATHS + [current])
    return env


def _shared_flags():
    return [
        "--cookies-from-browser", config.COOKIES_BROWSER,
        "--js-runtimes", config.JS_RUNTIME,
        "-f", config.VIDEO_FORMAT,
        "--merge-output-format", config.MERGE_FORMAT,
    ]


def build_channel_command(url):
    return [
        "yt-dlp",
        "-P", config.CHANNEL_DOWNLOAD_PATH,
        *_shared_flags(),
        "--write-subs",
        "--write-auto-subs",
        "--embed-subs",
        "--write-thumbnail",
        "--embed-thumbnail",
        "--write-info-json",
        "--embed-metadata",
        "--download-archive", config.CHANNEL_ARCHIVE_FILE,
        "--continue",
        "--ignore-errors",
        "--concurrent-fragments", config.CHANNEL_CONCURRENT_FRAGMENTS,
        "-o", config.CHANNEL_OUTPUT_TEMPLATE,
        url,
    ]


def build_single_command(url, path):
    return ["yt-dlp", "-P", path, *_shared_flags(), url]


def stream_output(pipe, line_queue):
    for line in pipe:
        line_queue.put(line)
    pipe.close()


def _monitor_process(proc, reader_threads, done_queue):
    for reader_thread in reader_threads:
        reader_thread.join()
    proc.wait()
    done_queue.put(proc.returncode)


def start_download(command, stdout_queue, stderr_queue, done_queue):
    proc = subprocess.Popen(
        command,
        env=build_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        preexec_fn=os.setsid,
    )

    stdout_thread = threading.Thread(target=stream_output, args=(proc.stdout, stdout_queue), daemon=True)
    stderr_thread = threading.Thread(target=stream_output, args=(proc.stderr, stderr_queue), daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    threading.Thread(
        target=_monitor_process, args=(proc, [stdout_thread, stderr_thread], done_queue), daemon=True
    ).start()

    return proc
