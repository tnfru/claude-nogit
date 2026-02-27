#!/bin/bash
set -e

if [ "$ENABLE_FIREWALL" = "1" ]; then
    echo "Initializing network firewall..."
    sudo /usr/local/bin/init-firewall.sh
fi

exec claude "$@"
