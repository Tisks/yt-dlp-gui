"""What a download batch is doing, and how its URLs group into yt-dlp runs."""

IDLE = "idle"
BUSY = "busy"
OK = "ok"
FAIL = "fail"


def status(pending, has_run, had_failure):
    """One of IDLE / BUSY / OK / FAIL, from a batch's counters."""
    if pending > 0:
        return BUSY
    if not has_run:
        return IDLE
    return FAIL if had_failure else OK


def should_forget_result(pending, has_run, has_any_url):
    """Whether a finished batch's ✓/✗ should be dropped.

    True once the user has cleared every URL out of the tab. Callers clear
    `has_run` rather than only hiding the glyph: otherwise typing a fresh URL
    would bring back a mark describing a batch that never ran on it.

    A running batch is never forgotten. Its ● is driven by the same counter
    that decides whether the tab may be closed, and a tab must never read as
    idle while yt-dlp is still writing files.
    """
    return not pending and has_run and not has_any_url


def group_downloads(entries):
    """Collect URL entries into one yt-dlp invocation per distinct set of flags.

    `entries` are (row, url, is_archive, playlist_items, cookies_browser).
    Returns [((is_archive, playlist_items, cookies_browser), rows, urls)], in
    first-seen order so the resulting processes start in the order the user
    typed their URLs.
    """
    groups = {}
    for row, url, is_archive, playlist_items, cookies_browser in entries:
        key = (is_archive, playlist_items, cookies_browser)
        rows, urls = groups.setdefault(key, ([], []))
        rows.append(row)
        urls.append(url)
    return [(key, rows, urls) for key, (rows, urls) in groups.items()]
