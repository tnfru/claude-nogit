# claude-nogit

Docker isolation wrapper for Claude Code. Copies a project (minus `.git`) into a container, runs Claude with `--dangerously-skip-permissions`, syncs changes back. Git history never enters the container.

## Architecture

```
claude-nogit (bash)          Entry point. Arg parsing, rsync copy, Docker orchestration, sync-back.
devcontainer/
  Dockerfile                 debian:bookworm-slim + native Claude binary. No Node.js.
  entrypoint.sh              Conditionally runs firewall init, then exec's claude.
  init-firewall.sh           iptables/ipset rules: allow only Anthropic, GitHub, npm, PyPI.
install.sh                   curl-to-bash installer. Downloads script + devcontainer to ~/.claude/.
```

Everything is bash. There is no build system, no package manager, no test framework.

## Key design decisions

- **rsync, not bind mount**: The project is copied to a temp dir, not mounted. This is the core safety guarantee — `.git` is physically absent from the container.
- **Throwaway git repo**: A fresh `git init` + `git commit` inside the temp copy creates a `baseline` tag so Claude can `git diff baseline` to see its own changes.
- **Session mapping**: Host project path is slugified (`/home/lars/code/foo` → `-home-lars-code-foo`). Container always sees `/workspace`, so sessions are stored under `-workspace` and remapped on sync-back.
- **Firewall opt-in**: `--firewall` enables `--cap-add=NET_ADMIN` + iptables. GitHub IPs fetched from `api.github.com/meta` at container startup. Other domains resolved via DNS and added to an ipset. IPv6 rejected outright. Off by default (`--no-firewall`).
- **Native binary, not npm**: Claude is downloaded as a platform binary during `docker build`, not installed via npm. Cuts image size from ~1.4GB to ~591MB.
- **Host-side resume**: `--continue` (default) syncs sessions back and `exec`s `claude --resume` on the host with normal permissions after the container exits. Session sync is extracted into `sync_sessions_to_host()` with a guard to prevent double-sync.
- **Signal handling**: `cleanup()` traps SIGINT/SIGTERM/EXIT. Calls `sync_sessions_to_host()`, preserves workspace in `/tmp` on failure for manual recovery.

## Working on this codebase

### Shell conventions

All scripts use `set -euo pipefail`. The main script (`claude-nogit`) temporarily disables `set -e` around `docker run` to capture exit codes. Arrays are used for argument building — no `eval` or string concatenation.

Color output: `GREEN` for success, `YELLOW` for warnings/progress, `RED` for errors. Use `echo -e` with `$NC` reset.

### Testing changes

There is no automated test suite. Test manually:

```bash
# Basic run (current directory)
./claude-nogit

# With firewall
./claude-nogit --firewall

# Without firewall
./claude-nogit --no-firewall

# Interactive mode (prompts before sync-back)
./claude-nogit --interactive

# Verify firewall blocks non-allowlisted traffic
# (init-firewall.sh has a built-in curl to example.com that must fail)

# Verify session persistence
./claude-nogit -- --resume
```

### Docker image

- Image name: `claude-code-dev`
- Build arg `CLAUDE_CODE_VERSION` is detected from host's `claude --version`
- Image label `claude.version` tracks the version; mismatch triggers auto-rebuild
- `--rebuild` flag forces a no-cache rebuild

### Adding allowed domains to the firewall

Edit `devcontainer/init-firewall.sh`. Add domains to the `for domain in ...` loop (line ~71). GitHub ranges are handled separately via the `/meta` API. After changes, test with `--rebuild` to force image rebuild.

### Sync-back logic

The rsync filters in `claude-nogit` are duplicated in two places: the initial copy and the sync-back (`SYNC_EXCLUDES`). Keep them in sync. Both use `--filter=':- .gitignore'` for per-directory .gitignore support.

### Common pitfalls

- **BSD vs GNU**: The script must work on macOS (BSD grep, no `-P` flag). Use `awk` for regex extraction instead of `grep -oP`.
- **Bash 3.2 compat**: macOS ships ancient bash. `${arr[@]+"${arr[@]}"}` guards empty arrays under `set -u`.
- **Docker DNS**: `init-firewall.sh` must save Docker's internal DNS NAT rules before flushing iptables, or DNS breaks inside the container.
