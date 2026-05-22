# autobox

Docker isolation wrapper for Claude Code. Creates a git worktree on a new branch, mounts it into a container with `.git` hidden behind a tmpfs, runs Claude with `--dangerously-skip-permissions`. Changes are written directly to disk — no sync needed.

## Architecture

```
autobox (bash)               Entry point. Arg parsing, worktree creation, Docker orchestration.
devcontainer/
  Dockerfile                 debian:bookworm-slim + native Claude binary. No Node.js.
  entrypoint.sh              Firewall init + throwaway git init on tmpfs, then exec's claude.
  init-firewall.sh           iptables/ipset rules: allow only Anthropic, GitHub, npm, PyPI.
install.sh                   curl-to-bash installer. Downloads script + devcontainer to ~/.claude/.
```

Everything is bash. There is no build system, no package manager, no test framework.

## Key design decisions

- **Worktree, not rsync**: A git worktree provides the project files on a new branch. Bind-mounted writable into the container. Changes are on disk immediately — no sync-back step.
- **tmpfs over .git**: The worktree's `.git` file (pointer to the main repo) is hidden by a tmpfs mount. The entrypoint creates a throwaway `git init` + `baseline` tag on the tmpfs so Claude can `git diff baseline`.
- **Session mapping**: Host project path is slugified (`/home/lars/code/foo` → `-home-lars-code-foo`). Container always sees `/workspace`, so sessions are stored under `-workspace` and remapped on sync-back. Session cwd is rewritten to the worktree path for `--continue`.
- **Firewall opt-in**: `--firewall` enables `--cap-add=NET_ADMIN` + iptables. GitHub IPs fetched from `api.github.com/meta` at container startup. Other domains resolved via DNS and added to an ipset. IPv6 rejected outright. Off by default (`--no-firewall`).
- **Native binary, not npm**: Claude is downloaded as a platform binary during `docker build`, not installed via npm. Cuts image size from ~1.4GB to ~591MB.
- **Host-side resume**: `--continue` (default) syncs sessions back and `exec`s `claude --resume` in the worktree dir with normal permissions.
- **Signal handling**: `cleanup()` traps SIGINT/SIGTERM/EXIT. Calls `sync_sessions_to_host()`, preserves worktree if changes exist, removes it if clean.

## Working on this codebase

### Shell conventions

All scripts use `set -euo pipefail`. The main script (`autobox`) temporarily disables `set -e` around `docker run` to capture exit codes. Arrays are used for argument building — no `eval` or string concatenation.

Color output: `GREEN` for success, `YELLOW` for warnings/progress, `RED` for errors. Use `echo -e` with `$NC` reset.

### Testing changes

There is no automated test suite. Test manually:

```bash
# Basic run (current directory)
./autobox

# With firewall
./autobox --firewall

# Without firewall
./autobox --no-firewall

# Verify worktree is created and changes persist
./autobox --no-continue
git -C /tmp/autobox-* status

# Verify firewall blocks non-allowlisted traffic
# (init-firewall.sh has a built-in curl to example.com that must fail)

# Verify session persistence
./autobox -- --resume
```

### Docker image

- Image name: `autobox-dev`
- Build arg `CLAUDE_CODE_VERSION` is detected from host's `claude --version`
- Image label `claude.version` tracks the version; mismatch triggers auto-rebuild
- `--rebuild` flag forces a no-cache rebuild
- Entrypoint always runs: handles firewall init + throwaway git init on the tmpfs

### Adding allowed domains to the firewall

Edit `devcontainer/init-firewall.sh`. Add domains to the `for domain in ...` loop (line ~71). GitHub ranges are handled separately via the `/meta` API. After changes, test with `--rebuild` to force image rebuild.

### Common pitfalls

- **BSD vs GNU**: The script must work on macOS (BSD grep, no `-P` flag). Use `awk` for regex extraction instead of `grep -oP`.
- **Bash 3.2 compat**: macOS ships ancient bash. `${arr[@]+"${arr[@]}"}` guards empty arrays under `set -u`.
- **Docker DNS**: `init-firewall.sh` must save Docker's internal DNS NAT rules before flushing iptables, or DNS breaks inside the container.
- **tmpfs over .git**: Docker's `--tmpfs /workspace/.git` shadows the worktree's `.git` file with an empty directory. The entrypoint detects this (no `.git/objects`) and runs `git init`.
