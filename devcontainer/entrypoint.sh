#!/bin/bash
set -e

if [ "$ENABLE_FIREWALL" = "1" ]; then
    echo "Initializing network firewall..."
    sudo /usr/local/bin/init-firewall.sh
fi

# Start Docker socket proxy if host socket is available
if [ -S "/var/run/docker-host.sock" ]; then
    echo "Starting Docker socket proxy..."
    python3 /usr/local/bin/docker-proxy.py &
    for i in $(seq 1 50); do
        [ -S "/var/run/docker.sock" ] && break
        sleep 0.1
    done
    if [ -S "/var/run/docker.sock" ]; then
        echo "Docker socket proxy ready"
    else
        echo "WARNING: Docker socket proxy failed to start"
    fi
fi

# In worktree mode, .git is a tmpfs — init a throwaway repo for git diff baseline
if [ -d "/workspace" ] && [ ! -d "/workspace/.git/objects" ]; then
    git -C /workspace init -q
    git -C /workspace add -A
    git -C /workspace -c user.name=baseline -c user.email=baseline -c commit.gpgsign=false commit -q -m "baseline" --allow-empty
    git -C /workspace tag baseline
fi

exec claude "$@"
