# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-19

### Added

- `linux-computer-use` skill for Claude Code, packaged as a plugin with its own marketplace manifest.
- `cu.py` commands: `shot`, `zoom`, `click`, `move`, `drag`, `scroll`, `type`, `key`, `windows`, `focus`, `clean`.
- `--into REGEX` guard on `type` and `key`.
- Screenshots scaled to 1280 px with automatic mapping of coordinates back to screen pixels.
- Private per-user state directory (mode 0700) with symlink and ownership checks.
- `install.sh` for installing as a personal skill.
- Unit tests, X11 integration tests under Xvfb, and CI on Ubuntu 22.04 and 24.04.

[Unreleased]: https://github.com/arif481/linux-computer-use/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/arif481/linux-computer-use/releases/tag/v0.1.0
