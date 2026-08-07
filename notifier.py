import subprocess


def _escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify(title, message):
    script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
    subprocess.Popen(["osascript", "-e", script])
