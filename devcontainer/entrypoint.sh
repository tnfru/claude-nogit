#!/bin/bash
set -e

if [ "$ENABLE_FIREWALL" = "1" ]; then
    echo "Initializing network firewall..."
    sudo /usr/local/bin/init-firewall.sh
fi

# In worktree mode, .git is a tmpfs — init a throwaway repo for git diff baseline
if [ -d "/workspace" ] && [ ! -d "/workspace/.git/objects" ]; then
    git -C /workspace init -q
    git -C /workspace add -A
    git -C /workspace -c user.name=baseline -c user.email=baseline -c commit.gpgsign=false commit -q -m "baseline" --allow-empty
    git -C /workspace tag baseline
fi

exec claude "$@"
