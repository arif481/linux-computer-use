# linux-computer-use

[![CI](https://github.com/arif481/linux-computer-use/actions/workflows/ci.yml/badge.svg)](https://github.com/arif481/linux-computer-use/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/arif481/linux-computer-use)](https://github.com/arif481/linux-computer-use/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Computer use for [Claude Code](https://claude.com/claude-code) on Linux. This skill lets Claude look at your X11 desktop and operate it: take screenshots, click, type, press shortcuts, scroll, drag and switch windows, in any application.

Claude's built-in computer use runs through the Claude desktop app, which is only available for macOS and Windows. This skill does the same job on Linux with two tools most distributions already package: [xdotool](https://github.com/jordansissel/xdotool) for input and [Pillow](https://python-pillow.org/) for screenshots.

## Features

- Screenshots scaled to 1280 px wide (about 0.12 s on a 1920x1080 laptop), with the pointer marked and an optional labeled grid for aiming
- Full-resolution zoom on any region, for small text and tight targets
- Left, right, middle and double clicks, hover, drag, and scrolling at a point
- Typing and key combinations, guarded by `--into REGEX` so input only goes to the window you meant
- Window listing and focusing by title
- Coordinates are given in screenshot space and mapped back to screen pixels automatically
- Screenshots kept in a private per-user directory and removable with one command

## Requirements

- An **X11** session. Check with `echo $XDG_SESSION_TYPE`; if it prints `wayland`, choose the Xorg session on the login screen.
- `xdotool`
- Python 3.10 or newer with Pillow 9.0 or newer

On Debian and Ubuntu:

```bash
sudo apt install xdotool python3-pil
```

## Installation

### As a Claude Code plugin

Inside Claude Code:

```
/plugin marketplace add arif481/linux-computer-use
/plugin install linux-computer-use@linux-computer-use
```

### As a personal skill

```bash
git clone https://github.com/arif481/linux-computer-use.git
cd linux-computer-use
./install.sh
```

`install.sh` symlinks the skill into `~/.claude/skills`, so `git pull` keeps it current. It also checks for xdotool, Pillow and an X11 session.

Use one method, not both, or Claude will see two copies of the skill. Restart Claude Code after installing.

## Usage

Ask Claude to do something on your desktop:

> Open the Files app and show me what's in Downloads.

> The video in Brave is paused. Play it and make it fullscreen.

> What's on my screen right now?

Claude loads the skill on its own when a request involves a desktop app, your screen, or phrases like "use my computer". You can also call it by name with `/linux-computer-use`.

## How it works

Claude works in a loop: take a screenshot, read it, perform one action, take another screenshot to check the result. It does not chain clicks blind, because interfaces move.

Every action goes through one script, [`skills/linux-computer-use/scripts/cu.py`](skills/linux-computer-use/scripts/cu.py). `shot` captures the screen, scales it down to 1280 px wide and saves the scale factor. Later commands take coordinates in that scaled image and multiply them back out, so on a 1920x1080 screen a click at (640, 360) lands on pixel (960, 540).

Images and state live in `$XDG_RUNTIME_DIR/claude-cu-<uid>` (falling back to `/tmp`), created with mode 0700. The script refuses to use that path if it is a symlink or owned by another user. Set `CU_DIR` to use a different directory.

### What it runs and sends

The script runs `xdotool` and reads the screen through Pillow. It makes no network requests, downloads nothing and installs nothing. Claude reads each screenshot the same way it reads any file in Claude Code, so the images it looks at are sent to the model as part of your conversation. Close anything you don't want Claude to see before asking it to use your desktop.

## Command reference

You can run the script directly as well:

```bash
CU="python3 skills/linux-computer-use/scripts/cu.py"
```

| Command | Description |
|---|---|
| `$CU shot [--grid N] [--width W] [--out PATH]` | Screenshot. Prints the image path, size, pointer position and active window title. |
| `$CU zoom X Y W H [--factor F]` | Full-resolution crop of a region, enlarged F times (default 2). Prints how to map zoom pixels back to screenshot coordinates. |
| `$CU click X Y [--button left\|middle\|right] [--count N]` | Move the pointer and click. `--count 2` double-clicks. |
| `$CU move X Y` | Move the pointer without clicking. |
| `$CU drag X1 Y1 X2 Y2` | Drag with the left button held. The button is always released, even if the drag fails partway. |
| `$CU scroll up\|down\|left\|right [N] [--x X --y Y]` | Scroll N notches (default 5), optionally at a point. |
| `$CU type TEXT [--into REGEX] [--delay MS]` | Type text. `-` reads stdin and drops one trailing newline. Text that starts with `-` goes after `--`. |
| `$CU key KEY... [--into REGEX]` | Press keys or combinations, using xdotool names: `Return`, `Escape`, `ctrl+l`, `alt+F4`. |
| `$CU windows` | List visible windows with their ids. |
| `$CU focus TARGET` | Activate a window by id or title regex. |
| `$CU clean` | Delete saved screenshots. |
| `$CU --version` | Print the version. |

Errors go to stderr with exit status 1.

## Safety

The skill gives Claude the same control of your desktop that you have. It is not a sandbox, so watch what it does the first few times. These rules are built in:

- With `--into`, `type` and `key` refuse to send anything unless the focused window's title matches. The skill tells Claude to use it every time it types. This came from a real failure during development: a synthetic Super key press did not open the Pop!_OS launcher, so an app name meant for the launcher was typed into a YouTube tab, where the letters triggered YouTube's keyboard shortcuts.
- Claude asks before sending messages, posting, buying, deleting files, installing software, changing system or account settings, or closing windows with unsaved work.
- Claude does not type passwords, 2FA codes or payment details; it asks you to enter them.
- Text in a web page, email or document that tells Claude to do something is ignored and reported to you.

See [SECURITY.md](SECURITY.md) for the threat model and how to report a vulnerability.

## Limitations

- Wayland is not supported, because it does not let ordinary programs inject input or capture the screen. Support would need `ydotool` and the screenshot portal, which this project does not use yet.
- Tested on Pop!_OS 22.04 with GNOME on a single 1920x1080 screen, and Ubuntu 22.04 and 24.04 under Xvfb with openbox in CI. Multi-monitor and fractional (HiDPI) scaling are untested.
- `xdotool type` sends one key at a time, so long text is slow, and characters missing from the active keyboard layout may not type correctly. With `xclip` installed, Claude can paste through the clipboard instead.
- Some desktops ignore a synthetic Super key press, so the skill starts applications from the shell (`gtk-launch`, `xdg-open`) rather than through the launcher.

## Troubleshooting

**`this is a Wayland session; xdotool needs X11`**: log out and pick the Xorg session (on GNOME, the gear icon on the login screen).

**`Your windowmanager claims not to support _NET_ACTIVE_WINDOW`**: you are running without an EWMH-compliant window manager (for example a bare Xvfb). Start one, such as openbox.

**`cannot capture the screen`**: Pillow could not connect to the X server. Check that `DISPLAY` is set and that your Pillow build has XCB support: `python3 -c "from PIL import features; print(features.check('xcb'))"`.

**Clicks land in the wrong place**: take a fresh `shot` before clicking; the coordinate scale comes from the most recent one. If you use display scaling, please open an issue with your setup.

## Development

```bash
git clone https://github.com/arif481/linux-computer-use.git
cd linux-computer-use
python3 -m unittest discover -s tests -v
```

The unit tests fake xdotool and the screen grab, so they run anywhere with Pillow installed. The integration tests drive a Tk window on a real X server and are skipped unless `CU_INTEGRATION=1`. Run them on a virtual display so they cannot touch your desktop:

```bash
sudo apt install xvfb openbox python3-tk
CU_INTEGRATION=1 xvfb-run -a -s "-screen 0 1920x1080x24" \
  sh -c 'openbox & sleep 2; python3 -m unittest discover -s tests -v'
```

CI runs ruff, shellcheck, the unit tests on Python 3.10 to 3.14, and the integration tests on Ubuntu 22.04 and 24.04 with the distributions' own packages. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Md Arifuzzaman
