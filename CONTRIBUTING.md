# Contributing

Bug reports, fixes and new commands are welcome. Please open an issue before starting on a large change so we can agree on the approach.

## Setup

You need an X11 session, `xdotool`, and Python 3.10+ with Pillow.

```bash
git clone https://github.com/arif481/linux-computer-use.git
cd linux-computer-use
./install.sh   # optional: use your checkout as your personal skill
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Unit tests (`tests/test_cu.py`) replace xdotool and the screen grab with fakes, so they never move your pointer. Integration tests (`tests/test_x11_integration.py`) drive a real Tk window and are skipped unless `CU_INTEGRATION=1`. Run them on a virtual display, never on your own desktop:

```bash
sudo apt install xvfb openbox python3-tk
CU_INTEGRATION=1 xvfb-run -a -s "-screen 0 1920x1080x24" \
  sh -c 'openbox & sleep 2; python3 -m unittest discover -s tests -v'
```

## Style

- Lint with [ruff](https://docs.astral.sh/ruff/): `ruff check .` (settings are in `pyproject.toml`).
- Check `install.sh` with `shellcheck install.sh`.
- `cu.py` must stay a single file that depends only on the standard library and Pillow. People install it by copying a folder.
- Errors meant for the user raise `CuError`; `main()` prints them and exits with status 1.

## Pull requests

- Keep each pull request to one change, with a test that fails without it.
- If you add or change a command, update the command table in `skills/linux-computer-use/SKILL.md` (the instructions Claude reads) and in `README.md`.
- Add a line under "Unreleased" in `CHANGELOG.md`.
- Anything that affects safety (input routing, `--into`, the state directory) needs a clear explanation in the pull request description.

## Releases

1. Bump the version in `skills/linux-computer-use/scripts/cu.py`, `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
2. Move the "Unreleased" changelog entries under the new version.
3. Tag `vX.Y.Z` and publish a GitHub release with the changelog section as its notes.
