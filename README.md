# claude-nogit

### 🐳 Run Claude Code autonomously. Keep your git history safe.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
[![Docker](https://img.shields.io/badge/Docker-required-blue?logo=docker&logoColor=white)](https://www.docker.com/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-required-blueviolet)](https://claude.ai/download)

A Docker isolation wrapper that lets you use `--dangerously-skip-permissions` without the danger. Your `.git` never enters the container. Worst case: bad code you can review and revert.

## 💡 The Problem

Claude Code is most powerful with `--dangerously-skip-permissions` — it can edit files, run commands, and install packages without asking. But giving it access to `.git` means it could rewrite history, force-push, or delete branches.

**claude-nogit** removes that risk entirely. Your project is copied into a Docker container without `.git`, Claude works with full autonomy, and only file changes sync back. If Claude produces bad code, you `git diff` and revert. Your history is never at risk.

## ✨ Features

- 🔒 **Git Isolation** — `.git` is physically absent from the container; your history is untouchable
- 🛡️ **Network Firewall** — Restricts outbound traffic to Anthropic API, GitHub, npm, and PyPI
- 🔁 **Session Continuity** — Resume conversations across runs, or continue on host after sync-back
- 🔄 **Auto-Rebuild** — Docker image rebuilds automatically when your local Claude version updates
- 📦 **Lightweight Image** — `debian:bookworm-slim` with native Claude binary (~591MB vs ~1.4GB with Node.js)
- 🚫 **`.gitignore` Aware** — Skips files your project already ignores
- ➡️ **Arg Passthrough** — Anything after `--` goes straight to Claude

## 🔬 How It Works

```
  HOST                                         CONTAINER
 ──────                                       ─────────

  project/                                     /workspace
  ├── .git/  ✗ stays on host                   ├── src/
  ├── src/   ─── rsync (no .git) ──────────>   ├── package.json
  ├── ...                                      └── ...
  │
  │            file changes                    Claude runs with full
  │          <── rsync back ───────────────    --dangerously-skip-permissions
  │
  ~/.claude/                                   /home/node/.claude/
  ├── credentials ──────────────────────────>  ├── credentials
  ├── settings    ──────────────────────────>  ├── settings
  └── sessions    <────────────────────────>   └── sessions
```

1. 📋 **Copy** — `rsync` your project to a temp dir, excluding `.git` and respecting `.gitignore`
2. 🐳 **Isolate** — Temp copy is mounted in a container with the native Claude binary and a network firewall
3. 🚀 **Run** — Claude starts with `--dangerously-skip-permissions` and full autonomy
4. 🔄 **Sync** — On exit, file changes copy back; sessions persist for `--resume`
5. 🔁 **Continue** — Claude resumes on the host with normal permissions for review

## 📦 Installation

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

**Prerequisites:** [Docker](https://www.docker.com/) and [Claude Code](https://claude.ai/download)

## 🚀 Quick Start

```bash
# Run in current directory
claude-nogit

# Run on a specific project
claude-nogit /path/to/project

# Pass arguments to Claude
claude-nogit -- --resume

# Skip the host-side review session
claude-nogit --no-continue
```

Claude launches with `--dangerously-skip-permissions` inside the container, does its work, syncs changes back, and resumes on the host with normal permissions so you can review what it did.

## 🛡️ What's Protected

| | Threat | Protection |
|---|--------|------------|
| 🔨 | `git push --force` | `.git` is physically absent from the container |
| 💥 | `git reset --hard` | No git history to reset |
| ✏️ | Rewrite commit history | No commits to rewrite |
| 🗑️ | Delete branches | No branches to delete |
| 🌐 | Exfiltrate code via network | Firewall restricts traffic to Anthropic, GitHub, npm, and PyPI |
| 📂 | Modify files outside project | Container filesystem isolation |

## ⚙️ Options

| Flag | Description |
|------|-------------|
| `--firewall` | (default) Restrict outbound traffic to Anthropic API, GitHub, npm, and PyPI |
| `--no-firewall` | Unrestricted network access |
| `--continue` | (default) After sync-back, resume the session on host with normal permissions |
| `--no-continue` | Exit after sync-back instead of resuming |
| `--docker` | Mount Docker socket (lets Claude manage sibling containers) |
| `--network NAME` | Connect to a Docker network (e.g. for databases) |
| `--full` | Include `node_modules`, `.venv`, etc. (excluded by default for speed) |
| `--show-diff` | Display diff before syncing changes back |
| `--interactive` | Prompt before copying changes back |
| `--rebuild` | Force Docker image rebuild |
| `--purge-sessions` | Delete saved session/todo data for the project |
| `-- [args]` | Pass remaining arguments to Claude |

## 📖 Examples

```bash
# Let Claude fix all tests autonomously, then review on host
claude-nogit -- -p "fix all failing tests"

# Resume a previous conversation
claude-nogit -- --resume

# Review changes before they apply
claude-nogit --interactive

# Include dependencies for a complete environment
claude-nogit --full

# Connect to a local database
claude-nogit --network my-network

# Let Claude spin up sibling containers
claude-nogit --docker
```

## 🔎 How It Compares

| | claude-nogit | Bare `--dangerously-skip-permissions` | macOS `sandbox-exec` wrappers |
|---|---|---|---|
| **Git safety** | `.git` physically absent | `.git` fully writable | `.git` writable (within project dir) |
| **Network control** | Firewall allowlist | Unrestricted | No network isolation |
| **Blast radius** | Container only | Entire system | Project directory |
| **Session continuity** | Resume on host after sync | N/A | Native |
| **Platform** | Linux, macOS (Docker) | Any | macOS only |
| **Overhead** | Container startup + rsync | None | Near zero |

## ❓ FAQ

<details>
<summary><strong>Why not just use Anthropic's devcontainer?</strong></summary>

The official devcontainer mounts your full project directory, including `.git`. This wrapper exists specifically to prevent that.
</details>

<details>
<summary><strong>Does this limit what Claude can do?</strong></summary>

No. Claude has full `--dangerously-skip-permissions` inside the container. It can edit any file, run any command, install packages — it just can't touch your git history or reach outside the container.
</details>

<details>
<summary><strong>What about .env files?</strong></summary>

They're copied into the container so Claude can use them. If this concerns you, add sensitive files to `.gitignore` (respected during copy) or exclude them manually.
</details>

<details>
<summary><strong>What if I Ctrl+C during a session?</strong></summary>

Sessions are synced back via a cleanup handler on SIGINT/SIGTERM. The workspace persists at `/tmp/claude-workspace-*` until reboot, with recovery instructions printed to the terminal.
</details>

<details>
<summary><strong>What does the firewall allow?</strong></summary>

Outbound traffic to Anthropic API, GitHub (IPs from their `/meta` endpoint), npm registry, PyPI, and Sentry/Statsig (for Claude's telemetry). Everything else is blocked via `iptables`. IPv6 is rejected entirely.
</details>

<details>
<summary><strong>What gets excluded by default?</strong></summary>

`.git/`, `.DS_Store`, `node_modules/`, `.venv/`, `__pycache__/`, `*.pyc`, and anything matched by your `.gitignore`. Use `--full` to include dependency directories.
</details>

## 🙏 Contributing

PRs welcome. Please test locally before submitting.

## 📄 License

[MIT](https://opensource.org/licenses/MIT)
