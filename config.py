import os

import platform_support

APP_NAME = platform_support.APP_NAME

TOOLS_BIN_DIR = platform_support.bundled_tools_bin_dir()
YT_DLP_NAME = "yt-dlp" + platform_support.EXECUTABLE_SUFFIX
YT_DLP_BIN = os.path.join(TOOLS_BIN_DIR, YT_DLP_NAME) if TOOLS_BIN_DIR else YT_DLP_NAME

# yt-dlp locates ffmpeg/ffprobe through PATH, so the bundled folder goes first.
EXTRA_PATHS = ([TOOLS_BIN_DIR] if TOOLS_BIN_DIR else []) + platform_support.SYSTEM_TOOL_PATHS

# The browsers the extension can report and the app can read cookies from.
COOKIE_BROWSERS = ("chrome", "firefox", "opera")
SUPPORTED_COOKIE_BROWSERS = set(COOKIE_BROWSERS)

# Preferred when more than one is installed; ignored if it isn't present.
PREFERRED_COOKIES_BROWSER = "chrome"
INSTALLED_COOKIE_BROWSERS = platform_support.installed_browsers(COOKIE_BROWSERS)
COOKIE_BROWSER_CHOICES = INSTALLED_COOKIE_BROWSERS or list(COOKIE_BROWSERS)
DEFAULT_COOKIES_BROWSER = (
    PREFERRED_COOKIES_BROWSER
    if PREFERRED_COOKIES_BROWSER in COOKIE_BROWSER_CHOICES
    else COOKIE_BROWSER_CHOICES[0]
)
# Auto-close only ever removes batches that finished cleanly, so a failed
# batch keeps its error log on screen.
AUTO_CLOSE_OFF = "Off"
AUTO_CLOSE_ON = "On"
AUTO_CLOSE_CHOICES = (AUTO_CLOSE_OFF, AUTO_CLOSE_ON)
DEFAULT_AUTO_CLOSE = AUTO_CLOSE_OFF

JS_RUNTIME = "deno"
VIDEO_FORMAT = "bv*+ba/b"
MERGE_FORMAT = "mkv"

CHANNEL_ARCHIVE_FILENAME = "archive.txt"
CHANNEL_OUTPUT_TEMPLATE = "%(uploader)s/%(upload_date>%Y-%m-%d)s - %(title)s [%(id)s].%(ext)s"
CHANNEL_CONCURRENT_FRAGMENTS = "8"

# Deliberately uppercase for the title bar; APP_NAME itself stays lowercase
# everywhere else (notifications, /ping identity, the settings folder).
WINDOW_TITLE = APP_NAME.upper()
WINDOW_GEOMETRY = platform_support.WINDOW_GEOMETRY

URL_SERVER_HOST = "127.0.0.1"
# The app binds the first free port in this range and the browser extension
# probes the same range to find it, so the two stay in sync without config.
URL_SERVER_PORT = 5005
URL_SERVER_PORT_SPAN = 11
URL_SERVER_PORTS = range(URL_SERVER_PORT, URL_SERVER_PORT + URL_SERVER_PORT_SPAN)
# Returned by /ping so the extension can tell our server from a stranger's.
URL_SERVER_IDENTITY = APP_NAME

URL_VALIDATE_TIMEOUT = 30
