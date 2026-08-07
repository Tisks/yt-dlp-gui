# yt-dlp-gui

A small Tkinter desktop front-end for `yt-dlp`, packaged as a native app for
macOS and Windows. The download tools (`yt-dlp`, `ffmpeg`, `ffprobe`, `deno`)
are bundled inside the app, so an end user installs one file and nothing else.

## Layout

The application code is shared across both platforms. Everything that differs
between operating systems lives in a single module.

```
download_app.py        entry point
gui.py                 Tkinter UI
downloader.py          builds and runs yt-dlp commands
url_server.py          localhost bridge the browser extension posts to
config.py              tunables and yt-dlp flags
notifier.py            desktop notifications (per-platform implementation)
platform_support.py    <- the only place that branches on sys.platform

chrome-extension/      browser extension (Chrome, Firefox and Opera)

packaging/
  macos/               spec, build scripts, .icns, DMG creation
  windows/             spec, build scripts, .ico, Inno Setup installer

vendor/                downloaded build inputs, git-ignored
  mac/{bin,lib}
  win/bin

.github/workflows/     CI that builds the Windows installer
```

### Adding platform-specific behaviour

Put the branch in `platform_support.py` and expose a name the rest of the app
can use unconditionally. It currently covers Tk cursor names, executable
suffixes, bundled-tool lookup, subprocess creation flags, process-tree
termination, mouse-wheel scaling, and default window size. `notifier.py` keeps
its own macOS/Windows implementations but takes the platform *detection* from
`platform_support`, so there is still one source of truth.

## Tests

```bash
python3 tests/run_tests.py            # everything
python3 tests/run_tests.py tabs port  # only suites matching these substrings
```

Each suite under `tests/` is a standalone script that prints its own checks and
exits non-zero on failure, so a single one can be run directly while working on
that area. `run_tests.py` sequences them and summarises; it exits non-zero if
anything fails, which is what gates the Windows installer build in CI.

The port suites need the app's default port free, so the runner refuses to
start (exit code 2) with a clear message if a copy of the app is already
running, rather than failing with a confusing assertion deep inside a test.

Suites spawn helper processes through `sys.executable` rather than `sleep` or
`true`/`false`, so they run on Windows as well as macOS. `test_windows_paths.py`
fakes `sys.platform` to exercise the Windows branches from a Mac; on the
Windows runner they also run for real.

## Building for macOS

Requires Homebrew: `brew install yt-dlp ffmpeg deno dylibbundler`.

```bash
./packaging/macos/fetch_vendor.sh   # populate vendor/mac (once, or to update tools)
./packaging/macos/release.sh        # build dist/macos/yt-dlp-gui.app, install to /Applications
./packaging/macos/make_dmg.sh       # produce dist/macos/yt-dlp-gui.dmg to share
```

`fetch_vendor.sh` copies the four tools and uses `dylibbundler` to pull in every
Homebrew dylib they need, rewriting their load paths to `@executable_path/../lib`
so the app runs on a machine with no Homebrew installed.

## Building for Windows

PyInstaller cannot cross-compile, so the Windows installer has to be produced on
Windows. There are two ways to do that.

### Via GitHub Actions (no Windows machine needed)

Push the repo to GitHub, then run the **Build Windows installer** workflow from
the Actions tab. It fetches the tools, builds the app, compiles the installer and
uploads `yt-dlp-gui-<version>-setup.exe` as a downloadable artifact. Pushing a
`v*` tag additionally attaches the installer to the GitHub release.

### On a Windows machine

Requires Python 3 (from python.org, with "Add to PATH" ticked) and Inno Setup 6.

```powershell
py -m pip install pyinstaller
winget install JRSoftware.InnoSetup

powershell -ExecutionPolicy Bypass -File packaging\windows\release.ps1 -Version 1.0.0
```

This writes `dist\windows\yt-dlp-gui-1.0.0-setup.exe`. Pass `-SkipInstaller` to
stop after the raw app folder, or `-SkipVendor` to reuse an existing
`vendor\win\bin`.

The installer defaults to a per-user install so it raises no UAC prompt; the
user can elevate to a machine-wide install from the wizard if they prefer.

## Cookies

`yt-dlp` reads cookies from a real browser profile so age-gated and
subscriber-only videos work. Two things decide which browser it reads:

- **URLs sent from the extension** carry the browser they came from, so a link
  sent from Firefox reads Firefox's cookies even if the dropdown says Chrome.
- **URLs typed into the app** follow the **Cookies from** dropdown, read at
  download time so changing it applies to rows already on screen.

The dropdown lists only browsers that actually have a profile on this machine
(`platform_support.installed_browsers`), checking the profile directory rather
than the application, since a browser that was installed but never launched has
no cookie database to read. If none of the three is detected, all three are
offered and the download reports the failure rather than guessing silently.

## Batches (tabs)

Each tab is one independent batch with its own URL rows, its own `yt-dlp`
processes, its own output/error logs and its own Download/Cancel. That is what
makes concurrent downloads readable: two batches running at once would
otherwise interleave their output into a single box with no way to tell the
lines apart, and Cancel could not target one of them.

Starting a download locks only that tab. Click `+` for a fresh tab and keep
queueing while the first one runs. Tab labels carry status -- `●` downloading,
`✓` finished, `✗` had a failure -- so you can see what is still running without
opening each one.

The first tab is permanent; the rest carry a `✕`. A tab that is downloading
refuses to close. Setting **Auto-close finished tabs** to `On` removes batches
once they finish, but only successful ones -- a failed batch keeps its tab so
the error log survives.

Path and the browser dropdown are shared above the tabs and apply to every
batch, so a new tab needs no re-entry.

### Implementation notes

Two ttk behaviours shape this code and are easy to trip over again:

- `<<NotebookTabChanged>>` is delivered **asynchronously**, after the event
  loop turns. A `try/finally` guard around `insert`/`select` is therefore
  already reset by the time the event lands, which made the `+` tab spawn a
  cascade of tabs. The latch in `_on_tab_changed` is instead held until the
  spawned tab exists.
- macOS Aqua ignores custom ttk tab elements, so a real close button cannot be
  styled onto a tab. The `✕` is part of the tab's text and clicks are
  hit-tested by hand in `_tab_close_hit`, measuring the tab's right edge with
  `notebook.index("@x,y")`.

## Settings

The download path and the cookie browser are remembered between launches in a
small JSON file, so neither has to be retyped:

| macOS | `~/Library/Application Support/yt-dlp-gui/settings.json` |
|---|---|
| Windows | `%APPDATA%\yt-dlp-gui\settings.json` |

It lives there rather than beside the executable because writing inside the app
would break the macOS bundle signature and would need admin rights under
Program Files.

It is written at two moments: when a download successfully starts (the path has
just been validated, so only a folder that actually worked gets saved) and when
the window closes. A path that is currently invalid never replaces the last
known-good one.

Settings are a convenience and never a failure point. A missing, corrupt or
truncated file falls back to defaults instead of stopping startup; writes go to
a temp file and are renamed over the target so an interrupted write cannot leave
a half-written file behind. A saved browser that has since been uninstalled is
dropped in favour of a detected one, but a saved path that no longer exists is
kept deliberately -- seeing the familiar folder flagged with "Path doesn't
exist" is more useful than finding the field silently blank, which matters when
the folder lives on an external drive.

## Code signing

Neither build is signed. macOS shows a Gatekeeper warning on first launch
(right-click → Open bypasses it) and Windows shows a SmartScreen prompt
("More info" → "Run anyway"). Removing those requires a paid Apple Developer
account and an Authenticode certificate respectively.

## Browser extension

`chrome-extension/` works in Chrome, Firefox and Opera despite the directory
name. It posts the active tab's URL to the app on localhost, and carries which
browser it came from so `yt-dlp` reads cookies from the right one. It has to be
loaded manually as an unpacked/temporary extension.

### How the two find each other

There is no port to configure. The app binds the first free port in
**5005-5015**; the extension probes that same range, confirms it is really us by
checking that `GET /ping` answers `{"app": "yt-dlp-gui"}`, then caches the port
in `storage.local`. If the app later moves or restarts on a different port, the
next failed call clears the cache and triggers a rescan.

The `/ping` check matters because a bare open port proves nothing -- some
unrelated service could hold 5006, and without the identity check the extension
would happily POST your URLs to it.

A browser extension can't `import config`, so its copy of the port range and
identity string is generated rather than hand-kept in sync. `config.py` is the
only place that ever changes by hand; running

    python3 scripts/generate_extension_config.py

regenerates `chrome-extension/generated_config.js` and the `host_permissions`
list in `manifest.json` from it. `--check` reports whether the checked-in files
are stale without writing anything, so it is safe to wire into CI or run before
a commit. `generated_config.js` loads before `background.js` for Firefox (both
listed in `manifest.json`'s `background.scripts`, sharing one scope); Chrome's
service worker only loads `background.js` itself, so it pulls the file in via
`importScripts()` at the top, which MV3 supports for non-module service
workers.

If all eleven ports are somehow taken, the app asks for a port instead of
failing. Note that a port outside 5005-5015 is not reachable by the extension,
so the browser shortcuts stop working there; the app itself still runs and
manual URL entry is unaffected.
