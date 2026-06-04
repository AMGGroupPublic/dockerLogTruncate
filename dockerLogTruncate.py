#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# MIT License — Matt Lowe / Marl Scot (marl.scot.dev@gmail.com)
"""Truncate a Docker container's JSON log file, with shell tab-completion.

Wraps the common idiom::

    docker inspect --format='{{.LogPath}}' <container> | xargs truncate -s 0

into a portable, self-registering CLI. The command name is derived from this
script's own filename, so the file may be renamed to suit any workflow and
``--setup`` will register completion under the new name automatically.
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

__version__ = "0.1.0"

logger = logging.getLogger("dockerLogTruncate")

# Short timeout for any docker call made during diagnostics so --help / --check
# never hang on an unreachable or slow daemon.
_DOCKER_TIMEOUT = 2.0

# System-wide bash-completion drop-in directory (root install target).
_GLOBAL_COMPLETION_DIR = Path("/etc/bash_completion.d")
# System-wide command directory (root install target).
_GLOBAL_BIN_DIR = Path("/usr/local/bin")
# Per-user command directory (non-root install target).
_USER_BIN_DIR = Path.home() / ".local" / "bin"


# --------------------------------------------------------------------------- #
# Naming
# --------------------------------------------------------------------------- #
def prog_name() -> str:
    """Return the command name, derived from this script's filename.

    Any trailing ``.py`` is stripped so ``dockerLogTruncate.py`` invoked on the
    PATH registers as ``dockerLogTruncate``. Renaming the file changes the name
    everywhere (argparse prog, symlink, completion registration, alerts).
    """
    name = Path(sys.argv[0]).name
    if name.endswith(".py"):
        name = name[: -len(".py")]
    return name or "dockerLogTruncate"


def _marker_block(name: str) -> tuple[str, str, str]:
    """Return (start, body, end) lines for the per-user ~/.bashrc block."""
    start = f"# >>> {name} completion >>>"
    body = f'eval "$(register-python-argcomplete {name})"'
    end = f"# <<< {name} completion <<<"
    return start, body, end


def _bashrc_path() -> Path:
    return Path.home() / ".bashrc"


# --------------------------------------------------------------------------- #
# Container discovery / completion
# --------------------------------------------------------------------------- #
def list_containers() -> list[str]:
    """Return all container names plus short (12-char) IDs.

    Raises on docker failure; callers that must never raise (the completer)
    wrap this.
    """
    result = subprocess.run(
        ["docker", "ps", "-a", "--no-trunc", "--format", "{{.Names}}\n{{.ID}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=_DOCKER_TIMEOUT,
    )
    candidates: list[str] = []
    for line in result.stdout.splitlines():
        token = line.strip()
        if not token:
            continue
        candidates.append(token)
        # Full IDs are 64 hex chars; also offer the short form people see in `docker ps`.
        if len(token) == 64 and all(c in "0123456789abcdef" for c in token):
            candidates.append(token[:12])
    # De-dupe, preserve order.
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def container_completer(prefix: str, **kwargs: object) -> list[str]:
    """argcomplete completer for the container argument.

    Must never raise: a completer that raises corrupts the user's shell line.
    On any failure it returns ``[]`` and reports the reason to argcomplete's
    debug stream so ``--check`` / debugging can see it.
    """
    try:
        return list_containers()
    except Exception as exc:  # noqa: BLE001 - completer must swallow everything
        try:
            import argcomplete  # local import: keep module import cheap

            argcomplete.debug(f"container_completer failed: {exc}\n")
        except Exception:  # noqa: BLE001
            pass
        return []


# --------------------------------------------------------------------------- #
# Diagnostics (shared by --help epilog and --check)
# --------------------------------------------------------------------------- #
def _docker_daemon_ok() -> bool:
    try:
        return (
            subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=_DOCKER_TIMEOUT,
            ).returncode
            == 0
        )
    except Exception:  # noqa: BLE001
        return False


def completion_registered(name: str) -> bool:
    """True if completion for ``name`` is wired up in either location."""
    if (_GLOBAL_COMPLETION_DIR / name).exists():
        return True
    bashrc = _bashrc_path()
    if bashrc.exists():
        start, _, _ = _marker_block(name)
        try:
            return start in bashrc.read_text(encoding="utf-8")
        except OSError:
            return False
    return False


def is_setup_done() -> bool:
    """True only if a command is on PATH *and* completion is registered."""
    name = prog_name()
    return shutil.which(name) is not None and completion_registered(name)


def gather_status() -> list[tuple[str, bool, str]]:
    """Return [(label, ok, hint), ...] describing the runtime environment.

    Used verbatim by both the ``--help`` epilog and ``--check`` so the two can
    never drift. Every probe is guarded; nothing here may raise.
    """
    name = prog_name()
    status: list[tuple[str, bool, str]] = []

    try:
        import argcomplete  # noqa: F401

        status.append(("argcomplete module", True, ""))
    except Exception:  # noqa: BLE001
        status.append(("argcomplete module", False, "install: pip install argcomplete"))

    reg = shutil.which("register-python-argcomplete") is not None
    status.append(
        (
            "register-python-argcomplete",
            reg,
            "" if reg else "install the python3-argcomplete / argcomplete package",
        )
    )

    docker_bin = shutil.which("docker") is not None
    status.append(
        ("docker binary", docker_bin, "" if docker_bin else "install Docker")
    )

    if docker_bin:
        daemon = _docker_daemon_ok()
        status.append(
            (
                "docker daemon reachable",
                daemon,
                "" if daemon else "start docker / check permissions (sudo, docker group)",
            )
        )
    else:
        status.append(("docker daemon reachable", False, "install Docker first"))

    registered = completion_registered(name)
    status.append(
        (
            "completion registered",
            registered,
            "" if registered else f"run: {name} --setup",
        )
    )

    on_path = shutil.which(name) is not None
    status.append(
        (
            f"'{name}' on PATH",
            on_path,
            "" if on_path else f"run: {name} --setup (adds a symlink on PATH)",
        )
    )

    # Informational: container count (never a hard failure).
    try:
        count = len(list_containers())
        status.append((f"containers discoverable ({count})", True, ""))
    except Exception:  # noqa: BLE001
        status.append(
            ("containers discoverable", False, "docker must be reachable for completion")
        )

    return status


def _format_status_block(status: list[tuple[str, bool, str]]) -> str:
    lines = ["Environment status:"]
    width = max(len(label) for label, _, _ in status)
    for label, ok, hint in status:
        mark = "PASS" if ok else "FAIL"
        line = f"  [{mark}] {label.ljust(width)}"
        if not ok and hint:
            line += f"   -> {hint}"
        lines.append(line)
    return "\n".join(lines)


def cmd_check() -> int:
    """``--check`` / ``--doctor``: print diagnostics, exit non-zero on failure."""
    status = gather_status()
    print(_format_status_block(status))
    # Critical checks: completion can't work without these.
    critical = {"argcomplete module", "register-python-argcomplete", "docker binary"}
    failed = [label for label, ok, _ in status if not ok and label in critical]
    if failed:
        print(f"\nFAILED critical checks: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


# --------------------------------------------------------------------------- #
# Setup / teardown
# --------------------------------------------------------------------------- #
def _script_path() -> Path:
    return Path(__file__).resolve()


def _register_completion_text(name: str) -> str:
    """Return the shell completion code from register-python-argcomplete."""
    result = subprocess.run(
        ["register-python-argcomplete", name],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _ensure_symlink(link: Path, target: Path) -> bool:
    """Create ``link`` -> ``target`` if absent. Return True if created."""
    if link.exists() or link.is_symlink():
        return False
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    return True


def _remove_symlink_if_ours(link: Path, target: Path) -> bool:
    """Remove ``link`` only if it is a symlink pointing at ``target``."""
    if link.is_symlink() and link.resolve() == target:
        link.unlink()
        return True
    return False


def cmd_setup() -> int:
    name = prog_name()
    script = _script_path()
    is_root = os.geteuid() == 0

    if is_root:
        # System-wide install for all users.
        link = _GLOBAL_BIN_DIR / name
        if shutil.which(name) is None:
            if _ensure_symlink(link, script):
                logger.info("Linked %s -> %s", link, script)
        try:
            text = _register_completion_text(name)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.error("register-python-argcomplete failed: %s", exc)
            return 1
        _GLOBAL_COMPLETION_DIR.mkdir(parents=True, exist_ok=True)
        dropin = _GLOBAL_COMPLETION_DIR / name
        dropin.write_text(text, encoding="utf-8")
        logger.info("Wrote system-wide completion to %s", dropin)
        logger.info(
            "Tab completion enabled for ALL users in new shells. "
            "Open a new shell to use it now."
        )
        return 0

    # Per-user install.
    link = _USER_BIN_DIR / name
    if shutil.which(name) is None:
        if _ensure_symlink(link, script):
            logger.info("Linked %s -> %s", link, script)
        if str(_USER_BIN_DIR) not in os.environ.get("PATH", "").split(os.pathsep):
            logger.warning(
                "%s is not on your PATH; add it so '%s' is runnable.",
                _USER_BIN_DIR,
                name,
            )

    bashrc = _bashrc_path()
    start, body, end = _marker_block(name)
    existing = bashrc.read_text(encoding="utf-8") if bashrc.exists() else ""
    if start in existing:
        logger.info("Completion already present in %s", bashrc)
    else:
        block = f"\n{start}\n{body}\n{end}\n"
        with bashrc.open("a", encoding="utf-8") as fh:
            fh.write(block)
        logger.info("Added completion block to %s", bashrc)
    logger.info("Run 'source %s' or open a new shell to enable completion.", bashrc)
    return 0


def cmd_teardown() -> int:
    name = prog_name()
    script = _script_path()
    is_root = os.geteuid() == 0

    if is_root:
        dropin = _GLOBAL_COMPLETION_DIR / name
        if dropin.exists():
            dropin.unlink()
            logger.info("Removed %s", dropin)
        if _remove_symlink_if_ours(_GLOBAL_BIN_DIR / name, script):
            logger.info("Removed %s", _GLOBAL_BIN_DIR / name)
        logger.info("System-wide completion removed (affects new shells).")
        return 0

    bashrc = _bashrc_path()
    if bashrc.exists():
        start, _, end = _marker_block(name)
        lines = bashrc.read_text(encoding="utf-8").splitlines(keepends=True)
        kept: list[str] = []
        skipping = False
        removed = False
        for line in lines:
            if line.strip() == start:
                skipping = True
                removed = True
                continue
            if line.strip() == end:
                skipping = False
                continue
            if not skipping:
                kept.append(line)
        if removed:
            bashrc.write_text("".join(kept), encoding="utf-8")
            logger.info("Removed completion block from %s", bashrc)
    if _remove_symlink_if_ours(_USER_BIN_DIR / name, script):
        logger.info("Removed %s", _USER_BIN_DIR / name)
    logger.info("Open a new shell to drop the completion for this session.")
    return 0


# --------------------------------------------------------------------------- #
# Core: truncate
# --------------------------------------------------------------------------- #
def resolve_log_path(container: str) -> Path:
    """Resolve a container's JSON log path via ``docker inspect``."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.LogPath}}", container],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("docker binary not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or "").strip() or f"unknown container: {container}"
        raise SystemExit(msg) from exc
    path = result.stdout.strip()
    if not path:
        raise SystemExit(f"no log path for container: {container}")
    return Path(path)


def truncate_log(path: Path, dry_run: bool) -> int:
    name = prog_name()
    if dry_run:
        logger.info("[dry-run] would truncate %s to 0 bytes", path)
        return 0
    try:
        os.truncate(path, 0)
    except PermissionError:
        logger.error(
            "Permission denied writing %s. Docker logs are usually root-owned; "
            "re-run with: sudo %s <container>",
            path,
            name,
        )
        return 1
    except FileNotFoundError:
        logger.error(
            "Log file not found: %s (is the docker host this machine?)", path
        )
        return 1
    logger.info("Truncated %s", path)
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    name = prog_name()
    epilog = (
        "Examples:\n"
        f"  {name} --setup                enable tab-completion (per-user, or\n"
        f"                                system-wide with sudo)\n"
        f"  {name} my-container           truncate that container's log\n"
        f"  {name} --dry-run my-container show what would be truncated\n"
        f"  {name} --check                diagnose the environment\n\n"
        f"{_format_status_block(gather_status())}"
    )
    parser = argparse.ArgumentParser(
        prog=name,
        description=(
            "Truncate a Docker container's JSON log file to 0 bytes, with "
            "tab-completion of container names/IDs."
        ),
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    container_arg = parser.add_argument(
        "container",
        nargs="?",
        help="container name or ID whose log to truncate (Tab-completes)",
    )
    container_arg.completer = container_completer  # type: ignore[attr-defined]

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--setup",
        action="store_true",
        help="register shell completion and a PATH command, then exit",
    )
    mode.add_argument(
        "--teardown",
        action="store_true",
        help="remove what --setup installed, then exit",
    )
    mode.add_argument(
        "--check",
        "--doctor",
        dest="check",
        action="store_true",
        help="print an environment diagnostic and exit",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve and print the log path but do not truncate",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only show warnings and errors",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show debug output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _configure_logging(quiet: bool, verbose: bool) -> None:
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()

    try:
        import argcomplete

        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    args = parser.parse_args(argv)
    _configure_logging(args.quiet, args.verbose)

    if args.setup:
        return cmd_setup()
    if args.teardown:
        return cmd_teardown()
    if args.check:
        return cmd_check()

    if not args.container:
        parser.error("a container name or ID is required (or use --setup/--check)")

    if not args.quiet and not is_setup_done():
        logger.warning(
            "Tab completion is not enabled. Enable it with:  %s --setup",
            prog_name(),
        )

    path = resolve_log_path(args.container)
    return truncate_log(path, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
