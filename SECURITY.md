# Security policy

## Supported versions

Only the latest release receives fixes.

## Reporting a vulnerability

Please report security problems privately through GitHub: open the Security tab of this repository and choose "Report a vulnerability". Do not open a public issue for them.

Include what you found, how to reproduce it, and what an attacker could do with it.

## Threat model

This skill hands an AI agent the mouse and keyboard of a live desktop session. Keep these properties in mind when you use it or review changes to it.

### What it protects against

- Input reaching the wrong application. `type` and `key` accept `--into REGEX` and refuse to send anything unless the focused window's title matches. The skill instructs Claude to use it on every `type`.
- Other local users reading screenshots. Images and state are written to `$XDG_RUNTIME_DIR/claude-cu-<uid>` (or `/tmp/claude-cu-<uid>`) with mode 0700. The script refuses to use that path if it is a symlink or owned by another user, which blocks pre-creation and symlink attacks in shared `/tmp`.
- Accidental submits from piped text. `type -` drops the trailing newline that `echo` and heredocs add.

### What it does not protect against

- Prompt injection from the screen. Anything visible in a screenshot (web pages, emails, chat messages, documents) reaches the model. `SKILL.md` tells Claude to treat on-screen text as data and to ask before consequential actions, but that is an instruction to the model, not an enforced boundary.
- A compromised or misbehaving agent. The script can do whatever your user account can do through the GUI. It is not a sandbox. To contain it, run it in a separate X session, a virtual machine, or under Xvfb.
- Window title spoofing. `--into` trusts window titles, which any application can set.
- Screenshot contents. Screenshots can contain anything that was on screen. They stay on disk until `cu.py clean` is run or the runtime directory is cleared at logout.
