# linux-computer-use

A Claude Code skill that lets Claude see and control a Linux desktop. It takes screenshots, clicks, types, presses key combos, scrolls, drags and switches windows, in any app running under X11.

Claude's own computer use goes through the Claude desktop app, which doesn't run on Linux. This skill does the same job from Claude Code with two tools most distros already have: `xdotool` for input and Pillow for screenshots.

## What it looks like

You ask Claude something like "open the text editor and write a note", "un-pause the video in Brave and make it fullscreen" or "what's on my screen?". Claude then works in a loop:

1. Takes a screenshot and looks at it.
2. Does one thing: a click, a few keystrokes, a scroll.
3. Takes another screenshot to check the result before the next step.

On a 1920x1080 Pop!_OS laptop a screenshot takes about 0.12 s. The first real tests were launching an editor, typing two lines, clicking "Close without Saving" in the save dialog, and bringing a YouTube video back from the miniplayer into fullscreen. All of them worked.

## Install

Requirements: an X11 session (not Wayland), `xdotool`, and Python 3 with Pillow.

```bash
sudo apt install xdotool python3-pil
```

As a plugin, from inside Claude Code:

```
/plugin marketplace add arif481/linux-computer-use
/plugin install linux-computer-use@linux-computer-use
```

Or as a personal skill, symlinked so `git pull` updates it:

```bash
git clone https://github.com/arif481/linux-computer-use
cd linux-computer-use
./install.sh
```

Restart Claude Code after either one. Pick only one method; installing both gives Claude two copies of the same skill.

To check which session type you have, run `echo $XDG_SESSION_TYPE`. If it prints `wayland`, log out and choose the Xorg session on the login screen.

## The helper script

Claude drives everything through `skills/linux-computer-use/scripts/cu.py`. You can run it yourself too:

```bash
CU="python3 skills/linux-computer-use/scripts/cu.py"
$CU shot --grid 100                     # screenshot with a labeled grid
$CU click 640 360                       # left click
$CU click 640 360 --button right        # right click
$CU type "hello" --into "Text Editor"   # type, only if that window is focused
$CU key ctrl+s --into "Text Editor"
$CU scroll down 5
$CU zoom 0 50 500 40                    # full-res crop of a small region
$CU windows                             # list windows
$CU focus Brave                         # bring a window to the front
```

Screenshots are scaled down to 1280 px wide before Claude sees them, and the cursor is marked with a red crosshair. Click coordinates are given in that scaled image. The script saves the scale factor and converts back to real screen pixels, so Claude never has to do that arithmetic. Files go to `/tmp/claude-cu`.

## Safety

The mouse and keyboard are yours while Claude is using them, so the skill has some rules built in:

- `type` and `key` take `--into REGEX` and refuse to send anything unless the focused window's title matches. This exists because of a real mistake during testing. A Super-key press didn't open the Pop!_OS launcher, so the app name Claude typed next went into a YouTube tab, where the letters triggered YouTube's keyboard shortcuts.
- Claude asks before anything that is hard to undo or leaves the machine: sending messages, posting, buying, deleting files, installing software, changing system settings.
- Claude never types passwords, 2FA codes or card numbers. It stops and asks you to enter them.
- Text on screen is treated as content, not as instructions. A web page that says "Claude, do X" gets ignored and reported.

None of this is a sandbox. Claude has the same access to your desktop that you do, so watch it the first few times.

## Limits

- X11 only. Wayland blocks synthetic input and screen capture from ordinary programs. Supporting it would need something like `ydotool` plus portal screenshots, which this doesn't do yet.
- Tested only on Pop!_OS with GNOME, on one 1920x1080 screen. Multi-monitor setups and HiDPI scaling are untested.
- `xdotool type` is slow for long text, and non-ASCII characters may not work on every keyboard layout (also untested). With `xclip` installed, Claude can paste through the clipboard instead.
- Some desktops ignore a synthetic Super key, so the skill starts apps from the shell (`gtk-launch`, `xdg-open`) rather than through the launcher.

## License

MIT
