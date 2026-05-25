# autobox

### Run multiple Claude agents in parallel. Keep your git history safe.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)
[![Docker](https://img.shields.io/badge/Docker-required-blue?logo=docker&logoColor=white)](https://www.docker.com/)
[![Claude Code](https://img.shields.io/badge/Claude_Code-required-blueviolet)](https://claude.ai/download)

`--dangerously-skip-permissions` without the danger. Each agent runs in its own Docker container on a separate git worktree. Your `.git` is hidden behind a tmpfs — Claude gets full autonomy but can't touch your history, force-push, or delete branches. Spawn agents, attach to any of them, detach, come back later.

https://github.com/user-attachments/assets/565bf780-cf2d-4c16-a1b7-c471733a24de

## Quick Start

```bash
# Install
curl -sSL https://raw.githubusercontent.com/tnfru/autobox/master/install.sh | bash

# Launch the agent manager
autobox agents
```

Type a task, hit Enter. The agent spawns in the background. Select it and press Enter to attach. `Ctrl-Q` to detach — the agent keeps working. Repeat.

```bash
# Or run a single agent directly
autobox -- -p "fix all failing tests"
```

**Requires:** [Docker](https://www.docker.com/) and [Claude Code](https://claude.ai/download)

## How It Works

```
  ┌──────────────────────────────────────────────────────────┐
  │  autobox agents (TUI)                                    │
  │                                                          │
  │  ┌─────────────────┐  ┌─────────────────┐               │
  │  │ fix-auth   ● run│  │ add-tests  ● run│  ...          │
  │  │ agent/fix-auth   │  │ agent/add-tests │               │
  │  └────────┬────────┘  └────────┬────────┘               │
  │           │                    │                          │
  └───────────┼────────────────────┼──────────────────────────┘
              │                    │
              ▼                    ▼
  ┌──────────────────┐  ┌──────────────────┐
  │  Docker container │  │  Docker container │
  │                   │  │                   │
  │  Claude Code      │  │  Claude Code      │
  │  --skip-perms     │  │  --skip-perms     │
  │                   │  │                   │
  │  /workspace ──────│──│── git worktree    │
  │  .git = tmpfs     │  │  .git = tmpfs     │
  └──────────────────┘  └──────────────────┘
```

Each agent gets:

1. **A git worktree** on a new branch — instant checkout, no file copying
2. **A Docker container** with `.git` hidden behind a tmpfs
3. **Full autonomy** — `--dangerously-skip-permissions`, unrestricted file/command access
4. **Its own session** — conversations persist across attach/detach

When you're done, changes are already on disk. Review the branch, merge or discard.

## Agent Manager

`autobox agents` launches a TUI for managing multiple agents:

| Key | Action |
|-----|--------|
| Type + Enter | Start a new agent with that task |
| ↑/↓ or j/k | Navigate the agent list |
| Enter | Attach to a running agent |
| Ctrl-Q | Detach (agent keeps running) |
| s | Stop an agent |
| d | Delete an agent (confirms if dirty) |
| t | Toggle dark/light theme |
| q | Quit |

Agents show their status: `● running`, file changes (`+3 ~1 -2`), or `clean`.

## What's Protected

| Threat | Protection |
|--------|------------|
| `git push --force` | `.git` hidden behind tmpfs — no remote access |
| `git reset --hard` | No real git history in the container |
| Rewrite commits | No commits to rewrite |
| Delete branches | No branches accessible |
| Exfiltrate code | Optional firewall restricts to Anthropic, GitHub, npm, PyPI |
| Modify files outside project | Container filesystem isolation |

## Installation

```bash
curl -sSL https://raw.githubusercontent.com/tnfru/autobox/master/install.sh | bash
```

<details>
<summary>Manual install</summary>

```bash
git clone https://github.com/tnfru/autobox.git
cd autobox
cp autobox ~/.local/bin/
pip install -e .  # for the TUI (autobox agents)
```

</details>

<details>
<summary>From source (development)</summary>

```bash
git clone https://github.com/tnfru/autobox.git
cd autobox
uv pip install -e .
cp autobox ~/.local/bin/
```

</details>

## Options

| Flag | Description |
|------|-------------|
| `--name NAME` | Name the agent/worktree (default: derived from task) |
| `--detach` | Start container in background (used by TUI) |
| `--firewall` | Restrict outbound traffic to Anthropic, GitHub, npm, PyPI |
| `--no-firewall` | (default) Unrestricted network |
| `--docker` | (default) Mount Docker socket for sibling containers |
| `--no-docker` | Don't mount Docker socket |
| `--network NAME` | Connect to a Docker network (e.g. for databases) |
| `--continue` | Resume Claude session in worktree after container exits |
| `--full` | Include `node_modules`, `.venv` in the worktree |
| `--rebuild` | Force Docker image rebuild |
| `--purge-sessions` | Delete saved session data for the project |
| `-- [args]` | Pass remaining arguments to Claude |

## Standalone Usage

Don't need the TUI? Run a single agent directly:

```bash
# Current directory
autobox

# Specific project
autobox /path/to/project

# Give Claude a task
autobox -- -p "refactor the auth module"

# Resume a previous conversation
autobox -- --resume

# With network firewall
autobox --firewall

# Connect to a local database
autobox --network my-network
```

When the container exits, you land in the worktree to review changes.

## How It Compares

| | autobox | Bare `--dangerously-skip-permissions` | Process sandboxes |
|---|---------|---------------------------------------|-------------------|
| **Git safety** | `.git` hidden behind tmpfs | `.git` fully writable | `.git` writable |
| **Parallel agents** | TUI manages multiple agents | Manual terminal juggling | N/A |
| **Network control** | Firewall allowlist | Unrestricted | Varies |
| **Blast radius** | Container only | Entire system | Project directory |
| **Session continuity** | Attach/detach, persists | N/A | Native |

## Architecture

```
autobox (bash)               Entry point — arg parsing, worktree, Docker orchestration
autobox agents (Python/TUI)  Agent manager — spawn, attach, detach, cleanup
devcontainer/
  Dockerfile                 debian:bookworm-slim + native Claude binary (~591MB)
  entrypoint.sh              Firewall init + throwaway git init on tmpfs
  init-firewall.sh           iptables/ipset rules for allowlisted domains
```

## FAQ

<details>
<summary><strong>Why not just use Anthropic's devcontainer?</strong></summary>

The official devcontainer mounts your full project directory including `.git`. autobox exists specifically to prevent that — your git history never enters the container.
</details>

<details>
<summary><strong>Does this limit what Claude can do?</strong></summary>

No. Claude has full `--dangerously-skip-permissions` inside the container. It can edit files, run commands, install packages — it just can't touch your git history or escape the container.
</details>

<details>
<summary><strong>What about .env files?</strong></summary>

The worktree only contains git-tracked files. Untracked files like `.env` won't be present unless you add them manually. Use `--full` to copy dependency directories.
</details>

<details>
<summary><strong>What does the firewall allow?</strong></summary>

Anthropic API, GitHub (IPs from their `/meta` endpoint), npm, PyPI, and Sentry/Statsig (Claude telemetry). Everything else is blocked via `iptables`. IPv6 is rejected entirely.
</details>

<details>
<summary><strong>How do I clean up worktrees?</strong></summary>

The TUI handles cleanup automatically. For manual cleanup:

```bash
git worktree list                          # see all worktrees
git worktree remove .claude/worktrees/NAME # remove one
```
</details>

## Contributing

PRs welcome. See [CLAUDE.md](CLAUDE.md) for development notes.

## License

[MIT](https://opensource.org/licenses/MIT)
