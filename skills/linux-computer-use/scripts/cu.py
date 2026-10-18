#!/usr/bin/env python3
"""Desktop control for X11: screenshots via Pillow, input via xdotool.

Coordinates passed to input commands are in *screenshot* space (the
downscaled image Claude looks at). They are mapped back to real screen
pixels using the scale saved by the last `shot`.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageGrab

STATE_DIR = os.environ.get("CU_DIR", "/tmp/claude-cu")
STATE = os.path.join(STATE_DIR, "state.json")
MAX_W = 1280


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"scale": 1.0}


def save_state(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(st, f)


def real(x, y):
    s = load_state()["scale"]
    return round(float(x) * s), round(float(y) * s)


def xdo(*args):
    r = subprocess.run(["xdotool", *map(str, args)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"xdotool failed: {r.stderr.strip()}")
    return r.stdout.strip()


def cursor_xy():
    out = xdo("getmouselocation", "--shell")
    d = dict(line.split("=", 1) for line in out.splitlines())
    return int(d["X"]), int(d["Y"])


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


def cmd_shot(a):
    img = ImageGrab.grab()
    W, H = img.size
    scale = max(1.0, W / a.width)
    if scale > 1.0:
        img = img.resize((round(W / scale), round(H / scale)), Image.Resampling.LANCZOS)
    save_state({"scale": scale, "screen": [W, H], "shot": list(img.size)})
    cx, cy = cursor_xy()
    draw_cursor(ImageDraw.Draw(img), cx / scale, cy / scale)
    if a.grid:
        draw_grid(img, a.grid)
    os.makedirs(STATE_DIR, exist_ok=True)
    path = a.out or os.path.join(STATE_DIR, f"shot-{int(time.time() * 1000)}.png")
    img.save(path)
    win = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                         capture_output=True, text=True).stdout.strip()
    print(f"{path}\nsize={img.size[0]}x{img.size[1]} screen={W}x{H} "
          f"cursor={round(cx / scale)},{round(cy / scale)} active={win!r}")


def cmd_zoom(a):
    st = load_state()
    s = st["scale"]
    box = [round(v * s) for v in (a.x, a.y, a.x + a.w, a.y + a.h)]
    img = ImageGrab.grab(bbox=tuple(box))
    f = a.factor
    img = img.resize((img.size[0] * f, img.size[1] * f), Image.Resampling.LANCZOS)
    path = os.path.join(STATE_DIR, f"zoom-{int(time.time() * 1000)}.png")
    img.save(path)
    k = f * s
    print(f"{path}\nzoom pixel (px,py) -> shot coords ({a.x:g} + px/{k:g}, {a.y:g} + py/{k:g})")


def cmd_click(a):
    x, y = real(a.x, a.y)
    btn = {"left": 1, "middle": 2, "right": 3}[a.button]
    xdo("mousemove", "--sync", x, y)
    time.sleep(0.05)
    xdo("click", "--repeat", a.count, "--delay", 80, btn)
    print(f"clicked {a.button} x{a.count} at shot({a.x},{a.y}) -> screen({x},{y})")


def cmd_move(a):
    x, y = real(a.x, a.y)
    xdo("mousemove", "--sync", x, y)
    print(f"moved to screen({x},{y})")


def cmd_drag(a):
    x1, y1 = real(a.x1, a.y1)
    x2, y2 = real(a.x2, a.y2)
    xdo("mousemove", "--sync", x1, y1)
    xdo("mousedown", 1)
    steps = 15
    for i in range(1, steps + 1):
        xdo("mousemove", round(x1 + (x2 - x1) * i / steps), round(y1 + (y2 - y1) * i / steps))
        time.sleep(0.02)
    xdo("mouseup", 1)
    print(f"dragged screen({x1},{y1}) -> ({x2},{y2})")


def cmd_scroll(a):
    if a.x is not None:
        x, y = real(a.x, a.y)
        xdo("mousemove", "--sync", x, y)
    btn = {"up": 4, "down": 5, "left": 6, "right": 7}[a.direction]
    xdo("click", "--repeat", a.amount, "--delay", 30, btn)
    print(f"scrolled {a.direction} x{a.amount}")


def check_into(a):
    if not a.into:
        return
    win = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                         capture_output=True, text=True).stdout.strip()
    if not re.search(a.into, win, re.I):
        sys.exit(f"refusing: active window is {win!r}, expected /{a.into}/")


def cmd_type(a):
    check_into(a)
    text = sys.stdin.read() if a.text == "-" else a.text
    xdo("type", "--delay", a.delay, "--", text)
    print(f"typed {len(text)} chars")


def cmd_key(a):
    check_into(a)
    xdo("key", "--delay", 60, *a.keys)
    print("pressed " + " ".join(a.keys))


def cmd_windows(_a):
    ids = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "."],
                         capture_output=True, text=True).stdout.split()
    for wid in ids:
        name = subprocess.run(["xdotool", "getwindowname", wid],
                              capture_output=True, text=True).stdout.strip()
        if name:
            print(f"{wid}\t{name}")


def cmd_focus(a):
    target = a.target
    if not target.isdigit():
        ids = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", target],
                             capture_output=True, text=True).stdout.split()
        if not ids:
            sys.exit(f"no visible window matching {target!r}")
        target = ids[-1]
    xdo("windowactivate", "--sync", target)
    print(f"focused {target}: {xdo('getwindowname', target)}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("shot", help="screenshot (downscaled, cursor marked)")
    s.add_argument("--width", type=int, default=MAX_W)
    s.add_argument("--grid", type=int, default=0, help="overlay a labeled grid every N px")
    s.add_argument("--out")
    s.set_defaults(f=cmd_shot)

    s = sp.add_parser("zoom", help="full-res crop of a region given in shot coords")
    for n in ("x", "y", "w", "h"):
        s.add_argument(n, type=float)
    s.add_argument("--factor", type=int, default=2)
    s.set_defaults(f=cmd_zoom)

    s = sp.add_parser("click")
    s.add_argument("x", type=float)
    s.add_argument("y", type=float)
    s.add_argument("--button", choices=["left", "middle", "right"], default="left")
    s.add_argument("--count", type=int, default=1, help="2 = double-click")
    s.set_defaults(f=cmd_click)

    s = sp.add_parser("move")
    s.add_argument("x", type=float)
    s.add_argument("y", type=float)
    s.set_defaults(f=cmd_move)

    s = sp.add_parser("drag")
    for n in ("x1", "y1", "x2", "y2"):
        s.add_argument(n, type=float)
    s.set_defaults(f=cmd_drag)

    s = sp.add_parser("scroll")
    s.add_argument("direction", choices=["up", "down", "left", "right"])
    s.add_argument("amount", type=int, nargs="?", default=5)
    s.add_argument("--x", type=float)
    s.add_argument("--y", type=float)
    s.set_defaults(f=cmd_scroll)

    s = sp.add_parser("type", help="type text ('-' reads stdin)")
    s.add_argument("text")
    s.add_argument("--delay", type=int, default=12)
    s.add_argument("--into", help="only type if active window title matches this regex")
    s.set_defaults(f=cmd_type)

    s = sp.add_parser("key", help="xdotool key names, e.g. ctrl+l Return super")
    s.add_argument("keys", nargs="+")
    s.add_argument("--into", help="only press if active window title matches this regex")
    s.set_defaults(f=cmd_key)

    s = sp.add_parser("windows", help="list visible windows")
    s.set_defaults(f=cmd_windows)

    s = sp.add_parser("focus", help="activate window by id or name regex")
    s.add_argument("target")
    s.set_defaults(f=cmd_focus)

    a = p.parse_args()
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        sys.exit("Wayland session: xdotool cannot control it. Log in with 'Xorg' instead.")
    a.f(a)


if __name__ == "__main__":
    main()
