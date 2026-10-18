#!/usr/bin/env python3
"""Control an X11 desktop: screenshots via Pillow, mouse and keyboard via xdotool.

Coordinates passed to input commands are in screenshot space (the
downscaled image written by `shot`). They are mapped back to real screen
pixels using the scale saved by the last `shot`.
"""
import argparse
import glob
import json
import os
import re
import stat
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageGrab

__version__ = "0.1.0"

DEFAULT_WIDTH = 1280
try:
    LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1; Ubuntu 22.04 ships 9.0
    LANCZOS = Image.LANCZOS  # type: ignore[attr-defined]
BUTTONS = {"left": 1, "middle": 2, "right": 3}
SCROLL_BUTTONS = {"up": 4, "down": 5, "left": 6, "right": 7}
DRAG_STEPS = 15


class CuError(Exception):
    """An error meant for the user; main() prints it and exits with status 1."""


# --- state ----------------------------------------------------------------

def state_dir():
    """Return the directory for screenshots and state, creating it if needed.

    Defaults to a per-user directory with mode 0700, because screenshots can
    contain anything that was on screen. CU_DIR overrides the location.
    """
    custom = os.environ.get("CU_DIR")
    if custom:
        os.makedirs(custom, exist_ok=True)
        return custom
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    path = os.path.join(base, f"claude-cu-{os.getuid()}")
    os.makedirs(path, mode=0o700, exist_ok=True)
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise CuError(f"{path} is not a directory owned by you; set CU_DIR to a private directory")
    if st.st_mode & 0o077:
        os.chmod(path, 0o700)
    return path


def load_state() -> dict:
    try:
        with open(os.path.join(state_dir(), "state.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"scale": 1.0}


def save_state(state):
    path = os.path.join(state_dir(), "state.json")
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def new_image_path(kind):
    return os.path.join(state_dir(), f"{kind}-{int(time.time() * 1000)}.png")


def to_screen(x, y, scale=None):
    """Map screenshot coordinates to real screen pixels."""
    if scale is None:
        scale = load_state().get("scale", 1.0)
    return round(x * scale), round(y * scale)


# --- X11 access -------------------------------------------------------------

def xdotool(*args, check=True):
    """Run xdotool and return its stdout ('' on failure when check is False)."""
    try:
        r = subprocess.run(["xdotool", *map(str, args)], capture_output=True, text=True)
    except FileNotFoundError:
        raise CuError("xdotool is not installed (sudo apt install xdotool)") from None
    if r.returncode != 0:
        if check:
            raise CuError(f"xdotool {args[0]} failed: {r.stderr.strip() or r.returncode}")
        return ""
    return r.stdout.strip()


def grab(bbox=None):
    try:
        return ImageGrab.grab(bbox=bbox)
    except OSError as e:
        raise CuError(f"cannot capture the screen: {e}") from None


def active_window_name():
    return xdotool("getactivewindow", "getwindowname", check=False)


def cursor_position():
    out = xdotool("getmouselocation", "--shell")
    fields = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return int(fields["X"]), int(fields["Y"])


def require_window(pattern):
    """Raise unless the focused window's title matches pattern (case-insensitive)."""
    if not pattern:
        return
    try:
        rx = re.compile(pattern, re.I)
    except re.error as e:
        raise CuError(f"bad --into pattern {pattern!r}: {e}") from None
    name = active_window_name()
    if not rx.search(name):
        raise CuError(f"refusing: active window is {name!r}, expected /{pattern}/")


def check_session():
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        raise CuError("this is a Wayland session; xdotool needs X11 (log in with an Xorg session)")
    if not os.environ.get("DISPLAY"):
        raise CuError("DISPLAY is not set; run this inside an X11 session")


# --- drawing ----------------------------------------------------------------

def draw_cursor(draw, x, y, r=10):
    draw.ellipse([x - r, y - r, x + r, y + r], outline="red", width=3)
    draw.line([x - r - 6, y, x + r + 6, y], fill="red", width=2)
    draw.line([x, y - r - 6, x, y + r + 6], fill="red", width=2)


def draw_grid(img, step):
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for gx in range(0, w, step):
        draw.line([gx, 0, gx, h], fill=(255, 0, 255), width=1)
        draw.text((gx + 2, 2), str(gx), fill=(255, 0, 255))
    for gy in range(0, h, step):
        draw.line([0, gy, w, gy], fill=(255, 0, 255), width=1)
        draw.text((2, gy + 2), str(gy), fill=(255, 0, 255))


# --- commands ---------------------------------------------------------------

def cmd_shot(a):
    img = grab()
    sw, sh = img.size
    scale = max(1.0, sw / a.width)
    if scale > 1.0:
        img = img.resize((round(sw / scale), round(sh / scale)), LANCZOS)
    save_state({"scale": scale, "screen": [sw, sh], "shot": list(img.size)})
    cx, cy = cursor_position()
    draw_cursor(ImageDraw.Draw(img), cx / scale, cy / scale)
    if a.grid:
        draw_grid(img, a.grid)
    path = a.out or new_image_path("shot")
    img.save(path)
    print(f"{path}\nsize={img.size[0]}x{img.size[1]} screen={sw}x{sh} "
          f"cursor={round(cx / scale)},{round(cy / scale)} active={active_window_name()!r}")


def cmd_zoom(a):
    state = load_state()
    scale = state.get("scale", 1.0)
    left, top = to_screen(a.x, a.y, scale)
    right, bottom = to_screen(a.x + a.w, a.y + a.h, scale)
    left, top = max(left, 0), max(top, 0)
    if "screen" in state:
        right, bottom = min(right, state["screen"][0]), min(bottom, state["screen"][1])
    if right <= left or bottom <= top:
        raise CuError("zoom region is empty or off screen")
    img = grab(bbox=(left, top, right, bottom))
    img = img.resize((img.size[0] * a.factor, img.size[1] * a.factor), LANCZOS)
    path = new_image_path("zoom")
    img.save(path)
    k = a.factor * scale
    print(f"{path}\nzoom pixel (px,py) -> shot coords "
          f"({left / scale:g} + px/{k:g}, {top / scale:g} + py/{k:g})")


def cmd_click(a):
    x, y = to_screen(a.x, a.y)
    xdotool("mousemove", "--sync", x, y)
    time.sleep(0.05)
    xdotool("click", "--repeat", a.count, "--delay", 80, BUTTONS[a.button])
    print(f"clicked {a.button} x{a.count} at shot({a.x:g},{a.y:g}) -> screen({x},{y})")


def cmd_move(a):
    x, y = to_screen(a.x, a.y)
    xdotool("mousemove", "--sync", x, y)
    print(f"moved to shot({a.x:g},{a.y:g}) -> screen({x},{y})")


def cmd_drag(a):
    scale = load_state().get("scale", 1.0)
    x1, y1 = to_screen(a.x1, a.y1, scale)
    x2, y2 = to_screen(a.x2, a.y2, scale)
    xdotool("mousemove", "--sync", x1, y1)
    xdotool("mousedown", 1)
    try:
        for i in range(1, DRAG_STEPS + 1):
            xdotool("mousemove", round(x1 + (x2 - x1) * i / DRAG_STEPS),
                    round(y1 + (y2 - y1) * i / DRAG_STEPS))
            time.sleep(0.02)
    finally:
        xdotool("mouseup", 1, check=False)
    print(f"dragged screen({x1},{y1}) -> ({x2},{y2})")


def cmd_scroll(a):
    if (a.x is None) != (a.y is None):
        raise CuError("--x and --y must be given together")
    if a.x is not None:
        x, y = to_screen(a.x, a.y)
        xdotool("mousemove", "--sync", x, y)
    xdotool("click", "--repeat", a.amount, "--delay", 30, SCROLL_BUTTONS[a.direction])
    print(f"scrolled {a.direction} x{a.amount}")


def cmd_type(a):
    require_window(a.into)
    text = a.text
    if text == "-":
        # Drop the newline that `echo` and heredocs add; it would press Enter.
        text = sys.stdin.read()
        if text.endswith("\n"):
            text = text[:-1]
    xdotool("type", "--delay", a.delay, "--", text)
    print(f"typed {len(text)} chars")


def cmd_key(a):
    require_window(a.into)
    xdotool("key", "--delay", 60, *a.keys)
    print("pressed " + " ".join(a.keys))


def cmd_windows(_a):
    for wid in xdotool("search", "--onlyvisible", "--name", ".", check=False).split():
        name = xdotool("getwindowname", wid, check=False)
        if name:
            print(f"{wid}\t{name}")


def cmd_focus(a):
    target = a.target
    if not target.isdigit():
        ids = xdotool("search", "--onlyvisible", "--name", target, check=False).split()
        if not ids:
            raise CuError(f"no visible window matching {target!r}")
        target = ids[-1]
    xdotool("windowactivate", "--sync", target)
    print(f"focused {target}: {xdotool('getwindowname', target)}")


def cmd_clean(_a):
    files = glob.glob(os.path.join(state_dir(), "*.png"))
    for path in files:
        os.remove(path)
    print(f"removed {len(files)} images from {state_dir()}")


# --- CLI --------------------------------------------------------------------

def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def non_negative_int(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return value


def build_parser():
    p = argparse.ArgumentParser(prog="cu.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sp = p.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    s = sp.add_parser("shot", help="screenshot, downscaled, with the cursor marked")
    s.add_argument("--width", type=positive_int, default=DEFAULT_WIDTH,
                   help=f"maximum image width (default {DEFAULT_WIDTH})")
    s.add_argument("--grid", type=non_negative_int, default=0,
                   help="overlay a labeled grid every N pixels")
    s.add_argument("--out", help="write the image here instead of the state directory")
    s.set_defaults(func=cmd_shot)

    s = sp.add_parser("zoom", help="full-resolution crop of a region given in shot coords")
    for name in ("x", "y", "w", "h"):
        s.add_argument(name, type=float)
    s.add_argument("--factor", type=positive_int, default=2, help="enlargement (default 2)")
    s.set_defaults(func=cmd_zoom)

    s = sp.add_parser("click", help="move the pointer and click")
    s.add_argument("x", type=float)
    s.add_argument("y", type=float)
    s.add_argument("--button", choices=list(BUTTONS), default="left")
    s.add_argument("--count", type=positive_int, default=1, help="2 for a double-click")
    s.set_defaults(func=cmd_click)

    s = sp.add_parser("move", help="move the pointer (hover)")
    s.add_argument("x", type=float)
    s.add_argument("y", type=float)
    s.set_defaults(func=cmd_move)

    s = sp.add_parser("drag", help="drag with the left button held")
    for name in ("x1", "y1", "x2", "y2"):
        s.add_argument(name, type=float)
    s.set_defaults(func=cmd_drag)

    s = sp.add_parser("scroll", help="scroll the wheel, optionally at a point")
    s.add_argument("direction", choices=list(SCROLL_BUTTONS))
    s.add_argument("amount", type=positive_int, nargs="?", default=5)
    s.add_argument("--x", type=float)
    s.add_argument("--y", type=float)
    s.set_defaults(func=cmd_scroll)

    s = sp.add_parser("type", help="type text ('-' reads stdin)")
    s.add_argument("text")
    s.add_argument("--delay", type=non_negative_int, default=12, help="ms between keystrokes")
    s.add_argument("--into", metavar="REGEX",
                   help="refuse unless the active window title matches this regex")
    s.set_defaults(func=cmd_type)

    s = sp.add_parser("key", help="press keys, e.g. ctrl+l Return alt+F4")
    s.add_argument("keys", nargs="+")
    s.add_argument("--into", metavar="REGEX",
                   help="refuse unless the active window title matches this regex")
    s.set_defaults(func=cmd_key)

    s = sp.add_parser("windows", help="list visible windows")
    s.set_defaults(func=cmd_windows)

    s = sp.add_parser("focus", help="activate a window by id or title regex")
    s.add_argument("target")
    s.set_defaults(func=cmd_focus)

    s = sp.add_parser("clean", help="delete saved screenshots")
    s.set_defaults(func=cmd_clean, offline=True)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if not getattr(args, "offline", False):
            check_session()
        args.func(args)
    except CuError as e:
        print(f"cu.py: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
