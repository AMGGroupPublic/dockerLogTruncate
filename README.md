# dockerLogTruncate

A portable, single-file CLI that truncates a Docker container's JSON log file to
0 bytes — with Tab-completion of container names and IDs.

It wraps the usual idiom:

```bash
docker inspect --format='{{.LogPath}}' <container-id> | xargs truncate -s 0
```

…into a self-registering command so you never have to remember or paste a
container ID again — just type and press Tab.

## Requirements

- Python 3.10+
- [`argcomplete`](https://pypi.org/project/argcomplete/) (provides
  `register-python-argcomplete`). On Debian/Ubuntu: `apt install python3-argcomplete`,
  or `pip install argcomplete`.
- `docker` on the host.
- bash (completion is wired for bash).

## Install

Drop `dockerLogTruncate.py` anywhere on the server, make it executable, then run
setup:

```bash
chmod +x dockerLogTruncate.py

# Per-user install (~/.local/bin + ~/.bashrc):
./dockerLogTruncate.py --setup
source ~/.bashrc

# OR system-wide for all users (/usr/local/bin + /etc/bash_completion.d):
sudo ./dockerLogTruncate.py --setup
# open a new shell
```

`--setup` detects whether it is running as root and chooses the global or
per-user locations automatically.

### Rename to suit your workflow

The command name comes from the script's filename. Rename the file and re-run
setup — everything registers under the new name:

```bash
mv dockerLogTruncate.py dlt
./dlt --setup
source ~/.bashrc
dlt <Tab>      # completes container names/IDs
```

## Usage

```bash
dockerLogTruncate <Tab>              # complete a container name/ID
dockerLogTruncate my-container       # truncate that container's log
dockerLogTruncate --dry-run my-app   # show the log path, write nothing
dockerLogTruncate --check            # diagnose the environment
dockerLogTruncate --teardown         # undo what --setup installed
```

Docker log files are normally owned by root. If you hit a permission error,
re-run with `sudo`:

```bash
sudo dockerLogTruncate my-container
```

## Diagnostics

`--help` shows a live **Environment status** block, and `--check` (alias
`--doctor`) prints the same checks and exits non-zero if anything required for
completion is missing — so you can see at a glance what still needs installing
or configuring.

## License

MIT — see [LICENSE](LICENSE).
