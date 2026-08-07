import base64
import subprocess

import platform_support

NOTIFICATION_SECONDS = 3


def _escape_applescript(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _notify_macos(title, message):
    script = (
        f'display alert "{_escape_applescript(title)}" '
        f'message "{_escape_applescript(message)}" '
        f"giving up after {NOTIFICATION_SECONDS}"
    )
    subprocess.Popen(["osascript", "-e", script])


def _notify_windows(title, message):
    # Balloon tips are surfaced as normal toasts on Windows 10/11 and, unlike
    # the toast APIs, need no registered AppUserModelID to work unsigned.
    def quote(text):
        return "'" + text.replace("'", "''") + "'"

    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "Add-Type -AssemblyName System.Drawing;"
        "$n = New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon = [System.Drawing.SystemIcons]::Information;"
        "$n.Visible = $true;"
        f"$n.ShowBalloonTip({NOTIFICATION_SECONDS * 1000}, {quote(title)}, {quote(message)},"
        " [System.Windows.Forms.ToolTipIcon]::Info);"
        f"Start-Sleep -Seconds {NOTIFICATION_SECONDS};"
        "$n.Dispose()"
    )
    # -EncodedCommand sidesteps every layer of shell quoting between here and PowerShell.
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        **platform_support.subprocess_flags(),
    )


def notify(title, message):
    # A failed notification must never take the app down with it.
    try:
        if platform_support.IS_WINDOWS:
            _notify_windows(title, message)
        else:
            _notify_macos(title, message)
    except OSError:
        pass
