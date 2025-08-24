# claude-nogit

> Run Claude in Anthropic's devcontainer without exposing your .git folder

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Bash](https://img.shields.io/badge/bash-%23121011.svg?logo=gnu-bash&logoColor=white)](https://www.gnu.org/software/bash/)

## Features

- 🔒 **Git isolation** - `.git` folder never enters the container
- 🔍 **Change review** - See diffs before applying changes back
- 💾 **Selective sync** - Choose which changes to keep
- 🚀 **Auto-start** - Claude launches with `--dangerously-skip-permissions`
- 🔑 **Persistent auth** - Credentials preserved between sessions

## Installation

```bash
# Quick install
curl -sSL https://raw.githubusercontent.com/tnfru/claude-nogit/main/install.sh | bash

# Manual install
git clone https://github.com/tnfru/claude-nogit.git
cp claude-nogit/claude-nogit ~/.local/bin/
# Or add to PATH: export PATH="$PATH:$(pwd)/claude-nogit"
```

### Prerequisites
- Docker
- Claude CLI (`npm install -g @anthropic-ai/claude-code`)
- Anthropic's devcontainer files (auto-downloaded on first run)

## Usage

```bash
# Current directory (default)
claude-nogit

# Specific project
claude-nogit /path/to/project

# Include node_modules and .venv (default: excluded for speed)
claude-nogit --full

# Include dependencies for specific project
claude-nogit --full /path/to/project
```

## How it works

1. **Copies** project to `/tmp` excluding `.git`
2. **Mounts** the copy in Anthropic's official devcontainer
3. **Runs** Claude with full permissions
4. **Shows** changes after you exit
5. **Syncs** approved changes back (including deletions)

## Example

```bash
$ claude-nogit  # No argument - uses current directory
=== Safe Claude Code Runner ===
Project: /home/user/my-project
Safe workspace: /tmp/claude-workspace-12345

Fast mode: Excluding large dependency directories
Creating clean workspace...
✓ Mounting Claude configuration and authentication
Starting Claude container...
Claude will auto-start with --dangerously-skip-permissions

╭──────────────────────────╮
│ ✻ Welcome to Claude Code │
╰──────────────────────────╯

> What would you like to do?
[Work with Claude...]
[Exit with Ctrl+D]

=== Reviewing Changes ===
Changes:
Files backend/api.py and /tmp/claude-workspace-12345/backend/api.py differ
Only in /home/user/my-project/backend: deleted-file.js

Review changes with 'diff' command? (y/n) > y
[Shows unified diff]

Copy changes back to project? (y/n) > y
✓ Changes applied to project (including deletions)
```

## Configuration

The script excludes these by default in fast mode:
- `node_modules/`
- `.venv/`
- `__pycache__/`
- `*.pyc`

Always excluded:
- `.git/` and `.git*`
- `.DS_Store`

To modify, edit the `EXCLUDES` variable in the script.

## FAQ

**Why not just use Anthropic's devcontainer directly?**  
The devcontainer still mounts your entire project including `.git`. This wrapper ensures git isolation.

**Does this affect Claude's capabilities?**  
No. Claude runs with full `--dangerously-skip-permissions` inside the container.

**What about my .env files?**  
They're included so Claude can understand your project configuration.

**Can I use git inside the container?**  
No. The `.git` folder is completely excluded from the container.

## Contributing

PRs welcome! Please test locally before submitting.

## License

MIT