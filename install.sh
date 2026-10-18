#!/usr/bin/env bash
# Install the skill as a personal Claude Code skill (symlink, so `git pull` updates it).
# Alternative: install as a plugin with /plugin marketplace add arif481/linux-computer-use
set -euo pipefail

src="$(cd "$(dirname "$0")" && pwd)/skills/linux-computer-use"
dest="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/linux-computer-use"

if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
  echo "warning: this is a Wayland session; the skill needs X11 (pick an Xorg session at login)" >&2
fi
command -v xdotool >/dev/null || echo "missing xdotool: sudo apt install xdotool" >&2
if ! python3 -c "import PIL" 2>/dev/null; then
  echo "missing Pillow: sudo apt install python3-pil" >&2
elif ! python3 -c "from PIL import features; assert features.check('xcb')" 2>/dev/null; then
  echo "warning: this Pillow build lacks XCB support and cannot take screenshots" >&2
fi

mkdir -p "$(dirname "$dest")"
if [ -e "$dest" ] && [ ! -L "$dest" ]; then
  echo "error: $dest exists and is not a symlink; remove it first" >&2
  exit 1
fi
ln -sfn "$src" "$dest"
echo "linked $dest -> $src"
echo "restart Claude Code, then ask it to use your computer"
