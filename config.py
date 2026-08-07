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
WINDOW_GEOMETRY = "500x460"

URL_SERVER_HOST = "127.0.0.1"
URL_SERVER_PORT = 5005
