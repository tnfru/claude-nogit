# claude-nogit

<p align="center">
  <strong>Run Claude Code autonomously. Keep your git history safe.</strong>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-required-blue?logo=docker&logoColor=white" alt="Docker"></a>
  <a href="https://claude.ai/download"><img src="https://img.shields.io/badge/Claude_Code-required-blueviolet" alt="Claude Code"></a>
</p>

<p align="center">
  A Docker isolation wrapper that lets you use <code>--dangerously-skip-permissions</code> without the danger.<br>
  Your <code>.git</code> never enters the container. Worst case: bad code you can review and revert.
</p>

---

## Why?

Claude Code is most powerful with `--dangerously-skip-permissions` -- it can edit files, run commands, and install packages without asking. But giving it access to `.git` means it can rewrite history, force-push, or delete branches.

**claude-nogit** removes that risk. It copies your project (minus `.git`) into a Docker container, lets Claude go wild, then syncs the file changes back. Your git history stays untouched on the host. If Claude produces bad code, you just `git diff` and revert.

## Install

```bash
curl -sSL https://raw.githubusercontent.com/tnfru/claude-nogit/master/install.sh | bash
```

<details>
<summary>Manual install</summary>

```bash
git clone https://github.com/tnfru/claude-nogit.git
cp claude-nogit/claude-nogit ~/.local/bin/
# Ensure ~/.local/bin is in your PATH
```

</details>

**Prerequisites:** [Docker](https://www.docker.com/) and [Claude Code](https://claude.ai/download) (`curl -fsSL https://claude.ai/install.sh | bash`)

## Quick Start

```bash
# Run in current directory
claude-nogit

# Run on a specific project
claude-nogit /path/to/project

# Pass arguments to Claude
claude-nogit -- --model opus --resume

# Enable network firewall
claude-nogit --firewall
```

That's it. Claude launches with `--dangerously-skip-permissions` inside the container, does its work, and changes sync back automatically when it exits.

## How it works

```
  YOUR HOST                                    DOCKER CONTAINER
 ──────────                                   ─────────────────
                    rsync (no .git)
  project/  ──────────────────────────>  /workspace
  ├── .git/  (stays on host)               ├── src/
  ├── src/                                 ├── package.json
  ├── package.json                         └── ...
  └── ...
                                           Claude runs with full
  ~/.claude/                               --dangerously-skip-permissions
  ├── .credentials.json ──────────>  /home/node/.claude/
  ├── settings.json     ──────────>    ├── .credentials.json
  └── projects/                        ├── settings.json
      └── <project>/ <────────────     └── projects/
           (sessions synced back)          └── -workspace/
```

1. **Copy** -- `rsync` your project to a temp dir, excluding `.git` and respecting `.gitignore`
2. **Mount** -- Temp copy is mounted in a `debian:bookworm-slim` container with the native Claude binary
3. **Run** -- Claude starts with `--dangerously-skip-permissions` and full autonomy
4. **Sync** -- On exit, file changes are copied back; sessions and todos persist for next run
5. **Clean** -- Temp workspace is removed

## Features

- 🔒 **Git isolation** -- `.git` never enters the container; your history is untouchable
- 💬 **Session persistence** -- Resume conversations across runs with `-- --resume`
- 🛡️ **Network firewall** -- `--firewall` restricts traffic to Anthropic API, GitHub, and npm only
- 🔄 **Auto-rebuild** -- Docker image rebuilds automatically when your local Claude version updates
- 📦 **Lightweight image** -- `debian:bookworm-slim` with native Claude binary (~591MB vs ~1.4GB with Node.js)
- 🚫 **`.gitignore` aware** -- Skips files your project already ignores
- ➡️ **Arg passthrough** -- Anything after `--` goes straight to Claude

## Options

| Flag | Description |
|------|-------------|
| `--firewall` | Restrict network to Anthropic, GitHub, npm only |
| `--full` | Include `node_modules`, `.venv`, etc. (excluded by default for speed) |
| `--show-diff` | Display diff before syncing changes back |
| `--interactive` | Prompt before copying changes back |
| `--rebuild` | Force Docker image rebuild |
| `-h, --help` | Show help |
| `-- [args]` | Pass remaining arguments to Claude |

## Examples

```bash
# Let Claude fix all tests with full autonomy
claude-nogit -- -p "fix all failing tests"

# Network-restricted session on a specific project
claude-nogit --firewall /path/to/project

# Review changes before they apply
claude-nogit --show-diff

# Resume a previous conversation
claude-nogit -- --resume

# Full copy including dependencies, specific model
claude-nogit --full -- --model opus
```

## FAQ

**Why not just use Anthropic's devcontainer?**
The official devcontainer still mounts your full project directory, including `.git`. This wrapper exists specifically to prevent that.

**Does this limit what Claude can do?**
No. Claude has full `--dangerously-skip-permissions` inside the container. It can edit any file, run any command, install packages -- it just can't touch your git history.

**What about `.env` files?**
They're copied into the container so Claude can understand your project configuration. If this concerns you, add sensitive files to `.gitignore` (which is respected during copy) or exclude them manually.

**What if I exit unexpectedly (Ctrl+C)?**
Sessions are synced back via a cleanup handler on `SIGINT`/`SIGTERM`. Your workspace also persists at `/tmp/claude-workspace-*` until reboot.

**What does `--firewall` do exactly?**
Sets up `iptables` rules inside the container (via `--cap-add=NET_ADMIN`) to only allow outbound traffic to Anthropic API, GitHub, and npm registry. Everything else is blocked.

**What gets excluded by default?**
`.git/`, `.DS_Store`, `node_modules/`, `.venv/`, `__pycache__/`, `*.pyc`, and anything in your `.gitignore`. Use `--full` to include dependency directories.

## Contributing

PRs welcome. Please test locally before submitting.

## License

[MIT](https://opensource.org/licenses/MIT)
