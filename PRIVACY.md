# Privacy

linux-computer-use is a local tool. It has no server, no account, no analytics and no telemetry. This page describes exactly what it does with data on your machine.

## What it reads

- The contents of your screen, when Claude runs `cu.py shot` or `cu.py zoom`. Screenshots can contain anything that is visible, including names, email addresses and messages.
- Window titles and the pointer position, through `xdotool`.
- Text you pipe into `cu.py type -`.

## Where it stores data

Screenshots and a small state file (the last screenshot's scale and size) are written to `$XDG_RUNTIME_DIR/claude-cu-<uid>`, or `/tmp/claude-cu-<uid>` if that variable is unset. The directory is readable only by your user account. Files stay there until you run `cu.py clean`, delete them yourself, or log out (most distributions clear `$XDG_RUNTIME_DIR` at logout).

## What it sends

The plugin makes no network requests. When Claude reads a screenshot, Claude Code sends that image to Anthropic as part of your conversation, in the same way as any other file Claude reads. Anthropic's handling of conversation data is covered by [Anthropic's privacy policy](https://www.anthropic.com/legal/privacy).

Close or hide anything you don't want Claude to see before asking it to use your desktop.

## Contact

Questions about this page: open an issue at https://github.com/arif481/linux-computer-use/issues.
