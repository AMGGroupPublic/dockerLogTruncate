# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-04

### Added
- `dockerLogTruncate` single-file CLI that truncates a container's JSON log to
  0 bytes via `docker inspect` + `os.truncate`.
- Tab-completion of all container names and short IDs (`docker ps -a`) using
  argcomplete; the completer degrades to no candidates rather than breaking the
  shell when docker is unavailable.
- `--setup` / `--teardown` self-registration. Run as root it installs
  system-wide (`/usr/local/bin` + `/etc/bash_completion.d`); run as a normal
  user it installs per-user (`~/.local/bin` + `~/.bashrc`).
- Command name derived from the script filename, so the file can be renamed and
  `--setup` re-registers under the new name.
- `--check` / `--doctor` environment diagnostic, mirrored as a live status
  block in `--help`.
- Not-set-up warning on normal runs, `--dry-run`, `-q/--quiet`, `-v/--verbose`,
  `--version`, and a detect-and-warn message pointing at `sudo` on permission
  errors.
