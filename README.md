# gitjail

### 🐳 Run Claude Code autonomously. Keep your git history safe.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
[![Docker](https://img.shields.io/badge/Docker-required-blue?logo=docker&logoColor=white)](https://www.docker.com/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-required-blueviolet)](https://claude.ai/download)

Give Claude `--dangerously-skip-permissions` without the danger. Your `.git` never enters the container — Claude gets full autonomy over your code, but can't touch your history, force-push, or delete branches. When it's done, you land in the worktree to review everything it did.

## ✨ Features

- 🔒 **Git Isolation** — `.git` is hidden behind a tmpfs; your history is untouchable
- 🌿 **Worktree-Based** — Changes go to a git worktree on a new branch, not your working tree
- 🔁 **Session Continuity** — Claude resumes in the worktree with normal permissions for review
- 🛡️ **Network Firewall** — Optional allowlist restricting traffic to Anthropic, GitHub, npm, and PyPI
- 🐳 **Docker Socket** — Let Claude manage sibling containers with `--docker`
- 📦 **Lightweight Image** — `debian:bookworm-slim` with native Claude binary (~591MB vs ~1.4GB with Node.js)

## 🛡️ What's Protected

| | Threat | Protection |
|---|--------|------------|
| 🔨 | `git push --force` | `.git` is hidden behind a tmpfs inside the container |
| 💥 | `git reset --hard` | No real git history to reset |
| ✏️ | Rewrite commit history | No real commits to rewrite |
| 🗑️ | Delete branches | No branches accessible |
| 🌐 | Exfiltrate code via network | Firewall restricts traffic to Anthropic, GitHub, npm, and PyPI |
| 📂 | Modify files outside project | Container filesystem isolation |

## 📦 Installation

```bash
curl -sSL https://raw.githubusercontent.com/tnfru/gitjail/master/install.sh | bash
```

<details>
<summary>Manual install</summary>

```bash
git clone https://github.com/tnfru/gitjail.git
cp gitjail/gitjail ~/.local/bin/
# Ensure ~/.local/bin is in your PATH
```

</details>

**Prerequisites:** [Docker](https://www.docker.com/) and [Claude Code](https://claude.ai/download)

## 🚀 Quick Start

```bash
gitjail                              # run in current directory
gitjail /path/to/project             # run on a specific project
gitjail -- -p "fix all failing tests" # give Claude a task directly
gitjail -- --resume                  # resume a previous conversation
```

## ⚙️ Options

| Flag | Description |
|------|-------------|
| `--continue` | (default) After container exits, resume session in worktree with normal permissions |
| `--no-continue` | Drop into worktree shell without resuming Claude |
| `--firewall` | Restrict outbound traffic to Anthropic API, GitHub, npm, and PyPI |
| `--no-firewall` | (default) Unrestricted network access |
| `--docker` | Mount Docker socket (lets Claude manage sibling containers) |
| `--network NAME` | Connect to a Docker network (e.g. for databases) |
| `--full` | Include `node_modules`, `.venv`, etc. in the worktree |
| `--rebuild` | Force Docker image rebuild |
| `--purge-sessions` | Delete saved session/todo data for the project |
| `-- [args]` | Pass remaining arguments to Claude |

## 🔎 How It Compares

| | gitjail | Bare `--dangerously-skip-permissions` | Process-level sandboxes |
|---|---|---|---|
| **Git safety** | `.git` hidden behind tmpfs | `.git` fully writable | `.git` writable (within project dir) |
| **Network control** | Firewall allowlist | Unrestricted | Varies |
| **Blast radius** | Container only | Entire system | Project directory |
| **Session continuity** | Resumes in worktree | N/A | Native |
| **Platform** | Linux, macOS (Docker) | Any | OS-specific |
| **Overhead** | Worktree checkout + container startup | None | Near zero |

## 📖 Examples

```bash
# Let Claude fix all tests autonomously, then review in worktree
gitjail -- -p "fix all failing tests"

# Resume a previous conversation
gitjail -- --resume

# Restrict network access
gitjail --firewall

# Connect to a local database
gitjail --network my-network

# Let Claude spin up sibling containers
gitjail --docker

# Include dependencies in the worktree
gitjail --full
```

## 🔁 The Workflow

```
  ┌─────────────────────────────────────────────────────────┐
  │  CONTAINER (autonomous)                                 │
  │                                                         │
  │  Claude works with --dangerously-skip-permissions       │
  │  Full file access, commands, packages — no prompts      │
  │  .git is hidden behind a tmpfs                          │
  └──────────────────────┬──────────────────────────────────┘
                         │ container exits
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  WORKTREE (supervised)                                  │
  │                                                         │
  │  Changes are already on disk — no sync needed           │
  │  Same session resumes with normal permissions            │
  │  Review, commit, merge, or discard the branch           │
  └─────────────────────────────────────────────────────────┘
```

## 🔬 How It Works

```
  HOST                                         CONTAINER
 ──────                                       ─────────

  project/                                     /workspace
  ├── .git/ (main repo)                        ├── src/
  │                                            ├── package.json
  │   git worktree add                         └── ...
  │        ↓
  │   /tmp/gitjail-*/    ─── bind mount ───>   .git is a tmpfs (hidden)
  │   (new branch)                             throwaway git init for
  │                                            git diff baseline
  │
  ~/.claude/                                   /home/node/.claude/
  ├── credentials ──────────────────────────>  ├── credentials
  ├── settings    ──────────────────────────>  ├── settings
  └── sessions    <────────────────────────>   └── sessions
```

1. 🌿 **Worktree** — `git worktree add` creates a checkout on a new branch (instant, no file copying)
2. 🐳 **Isolate** — Worktree is bind-mounted into a container with `.git` hidden behind a tmpfs
3. 🚀 **Run** — Claude starts with `--dangerously-skip-permissions` and full autonomy
4. 📁 **Done** — Changes are already on disk in the worktree — no sync needed
5. 🔁 **Continue** — You land in the worktree shell; Claude resumes with normal permissions

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

The worktree only contains git-tracked files. Untracked files like `.env` won't be present. Use `--full` to copy dependency directories, or add specific files manually.
</details>

<details>
<summary><strong>What if I Ctrl+C during a session?</strong></summary>

Sessions are synced back via a cleanup handler on SIGINT/SIGTERM. If the worktree has changes, it's preserved with instructions for manual cleanup.
</details>

<details>
<summary><strong>What does the firewall allow?</strong></summary>

Outbound traffic to Anthropic API, GitHub (IPs from their `/meta` endpoint), npm registry, PyPI, and Sentry/Statsig (for Claude's telemetry). Everything else is blocked via `iptables`. IPv6 is rejected entirely.
</details>

<details>
<summary><strong>How do I clean up a worktree?</strong></summary>

```bash
git worktree remove /tmp/gitjail-*
```

If the worktree has no changes, gitjail cleans it up automatically.
</details>

## 🙏 Contributing

PRs welcome. Please test locally before submitting.

## 📄 License

[MIT](https://opensource.org/licenses/MIT)
