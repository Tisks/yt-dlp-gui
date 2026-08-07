import subprocess


def _escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify(title, message):
    # macOS suppresses Notification Center banners while a full-screen app has
    # focus, which is exactly when this app's alerts matter most. A modal
    # `display alert` still gets through, and `giving up after` auto-dismisses
    # it so it never blocks on user interaction.
    script = f'display alert "{_escape(title)}" message "{_escape(message)}" giving up after 3'
    subprocess.Popen(["osascript", "-e", script])
