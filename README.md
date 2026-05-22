# claude-nogit

### 🐳 Run Claude Code autonomously. Keep your git history safe.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
[![Docker](https://img.shields.io/badge/Docker-required-blue?logo=docker&logoColor=white)](https://www.docker.com/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-required-blueviolet)](https://claude.ai/download)

Give Claude `--dangerously-skip-permissions` without the danger. Your `.git` never enters the container — Claude gets full autonomy over your code, but can't touch your history, force-push, or delete branches. When it's done, you resume the same conversation on your host to review everything it did.

## ✨ Features

- 🔒 **Git Isolation** — `.git` is physically absent from the container; your history is untouchable
- 🔁 **Session Continuity** — Claude resumes on your host after sync-back for seamless review
- 🛡️ **Network Firewall** — Optional allowlist restricting traffic to Anthropic, GitHub, npm, and PyPI
- 🐳 **Docker Socket** — Let Claude manage sibling containers with `--docker`
- 🔄 **Auto-Rebuild** — Docker image rebuilds automatically when your local Claude version updates
- 📦 **Lightweight Image** — `debian:bookworm-slim` with native Claude binary (~591MB vs ~1.4GB with Node.js)

## 🛡️ What's Protected

| | Threat | Protection |
|---|--------|------------|
| 🔨 | `git push --force` | `.git` is physically absent from the container |
| 💥 | `git reset --hard` | No git history to reset |
| ✏️ | Rewrite commit history | No commits to rewrite |
| 🗑️ | Delete branches | No branches to delete |
| 🌐 | Exfiltrate code via network | Firewall restricts traffic to Anthropic, GitHub, npm, and PyPI |
| 📂 | Modify files outside project | Container filesystem isolation |

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
claude-nogit                              # run in current directory
claude-nogit /path/to/project             # run on a specific project
claude-nogit -- -p "fix all failing tests" # give Claude a task directly
claude-nogit -- --resume                  # resume a previous conversation
```

## ⚙️ Options

| Flag | Description |
|------|-------------|
| `--continue` | (default) After sync-back, resume the session on host with normal permissions |
| `--no-continue` | Exit after sync-back instead of resuming |
| `--firewall` | Restrict outbound traffic to Anthropic API, GitHub, npm, and PyPI |
| `--no-firewall` | (default) Unrestricted network access |
| `--docker` | Mount Docker socket (lets Claude manage sibling containers) |
| `--network NAME` | Connect to a Docker network (e.g. for databases) |
| `--full` | Include `node_modules`, `.venv`, etc. (excluded by default for speed) |
| `--show-diff` | Display diff before syncing changes back |
| `--interactive` | Prompt before copying changes back |
| `--rebuild` | Force Docker image rebuild |
| `--purge-sessions` | Delete saved session/todo data for the project |
| `-- [args]` | Pass remaining arguments to Claude |

## 🔎 How It Compares

| | claude-nogit | Bare `--dangerously-skip-permissions` | Process-level sandboxes |
|---|---|---|---|
| **Git safety** | `.git` physically absent | `.git` fully writable | `.git` writable (within project dir) |
| **Network control** | Firewall allowlist | Unrestricted | Varies |
| **Blast radius** | Container only | Entire system | Project directory |
| **Session continuity** | Resumes on host after sync | N/A | Native |
| **Platform** | Linux, macOS (Docker) | Any | OS-specific |
| **Overhead** | Container startup + rsync | None | Near zero |

## 📖 Examples

```bash
# Let Claude fix all tests autonomously, then review on host
claude-nogit -- -p "fix all failing tests"

# Resume a previous conversation
claude-nogit -- --resume

# Review changes before they apply
claude-nogit --interactive

# Restrict network access
claude-nogit --firewall

# Connect to a local database
claude-nogit --network my-network

# Let Claude spin up sibling containers
claude-nogit --docker
```

## 🔁 The Workflow

Most sandboxing tools are batch jobs — run the agent, get results, start a new session to review. claude-nogit keeps the conversation going:

```
  ┌─────────────────────────────────────────────────────────┐
  │  CONTAINER (autonomous)                                 │
  │                                                         │
  │  Claude works with --dangerously-skip-permissions       │
  │  Full file access, commands, packages — no prompts      │
  │  .git is physically absent                              │
  └──────────────────────┬──────────────────────────────────┘
                         │ changes sync back
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  HOST (supervised)                                      │
  │                                                         │
  │  Same session resumes with normal permissions            │
  │  Review changes, run /review-pr, ask questions          │
  │  git diff, commit, or revert                            │
  └─────────────────────────────────────────────────────────┘
```

The `--continue` flag (on by default) automatically resumes the session on your host after sync-back. Use `--no-continue` to exit instead.

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
2. 🐳 **Isolate** — Temp copy is mounted in a container with the native Claude binary
3. 🚀 **Run** — Claude starts with `--dangerously-skip-permissions` and full autonomy
4. 🔄 **Sync** — On exit, file changes copy back; sessions persist for `--resume`
5. 🔁 **Continue** — Claude resumes on the host with normal permissions for review

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
