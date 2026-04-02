#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, and pipeline failures
IFS=$'\n\t'       # Stricter word splitting

# 1. Extract Docker DNS info BEFORE any flushing
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

# Flush existing rules and delete existing ipsets
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# 2. Selectively restore ONLY internal Docker DNS resolution
if [ -n "$DOCKER_DNS_RULES" ]; then
    echo "Restoring Docker DNS rules..."
    iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
    iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
    # Only process actual rule lines (starting with -A) to avoid format issues
    while IFS= read -r rule; do
        if [[ "$rule" == -A* ]]; then
            iptables -t nat $rule || echo "WARNING: Failed to restore NAT rule: $rule"
        fi
    done <<< "$DOCKER_DNS_RULES"
else
    echo "No Docker DNS rules to restore"
fi

# Allow DNS to all configured nameservers (handles both Docker's 127.0.0.11 and host/Tailscale DNS)
while read -r dns_ip; do
    echo "Allowing DNS to $dns_ip"
    iptables -A OUTPUT -p udp --dport 53 -d "$dns_ip" -j ACCEPT
    iptables -A INPUT -p udp --sport 53 -s "$dns_ip" -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -d "$dns_ip" -j ACCEPT
    iptables -A INPUT -p tcp --sport 53 -s "$dns_ip" -j ACCEPT
done < <(awk '/^nameserver/ {print $2}' /etc/resolv.conf)
# Allow localhost
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Create ipset with CIDR support
ipset create allowed-domains hash:net

# Fetch GitHub meta information and aggregate + add their IP ranges
# If GitHub API is unreachable, skip GitHub ranges rather than blocking container startup
echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -s --connect-timeout 10 https://api.github.com/meta || true)

if [ -z "$gh_ranges" ] || ! echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null 2>&1; then
    echo "WARNING: Failed to fetch GitHub IP ranges — GitHub access will not be available"
else
    echo "Processing GitHub IPs..."
    while read -r cidr; do
        if [[ ! "$cidr" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]]; then
            echo "WARNING: Skipping invalid CIDR range from GitHub meta: $cidr"
            continue
        fi
        echo "Adding GitHub range $cidr"
        ipset add allowed-domains "$cidr"
    done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[]' | grep -v ':' | aggregate -q)
fi

# Resolve and add other allowed domains
# NOTE: IP-based filtering has inherent limitations with CDN-hosted services:
# - IPs are resolved at startup; CDN rotation during long sessions may break connectivity
# - Shared CDN IPs (e.g., Cloudflare) may also serve other domains on the same IP
# A forward proxy with SNI inspection would be more robust but adds complexity
for domain in \
    "registry.npmjs.org" \
    "api.anthropic.com" \
    "sentry.io" \
    "statsig.anthropic.com" \
    "statsig.com"; do
    echo "Resolving $domain..."
    ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
    if [ -z "$ips" ]; then
        echo "WARNING: Failed to resolve $domain — access to this service will not be available"
        continue
    fi

    while read -r ip; do
        if [[ ! "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
            echo "WARNING: Skipping invalid IP from DNS for $domain: $ip"
            continue
        fi
        echo "Adding $ip for $domain"
        ipset add allowed-domains "$ip"
    done < <(echo "$ips")
done

# Get host IP from default route
HOST_IP=$(ip route | grep default | cut -d" " -f3)
if [ -z "$HOST_IP" ]; then
    echo "ERROR: Failed to detect host IP"
    exit 1
fi

echo "Host gateway detected as: $HOST_IP"

# Set up remaining iptables rules — allow only the Docker gateway, not the entire /24
iptables -A INPUT -s "$HOST_IP" -j ACCEPT
iptables -A OUTPUT -d "$HOST_IP" -j ACCEPT

# Allow established connections for already approved traffic
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow only specific outbound traffic to allowed domains
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Set default policies to DROP last, after all ACCEPT rules are in place
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Block IPv6 with REJECT (not DROP) so apps fall back to IPv4 immediately
ip6tables -A INPUT -i lo -j ACCEPT
ip6tables -A OUTPUT -o lo -j ACCEPT
ip6tables -A INPUT -j REJECT
ip6tables -A OUTPUT -j REJECT
ip6tables -P INPUT DROP
ip6tables -P FORWARD DROP
ip6tables -P OUTPUT DROP

echo "Firewall configuration complete"
echo "Verifying firewall rules..."
if curl -4 --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo "ERROR: Firewall verification failed - was able to reach https://example.com"
    exit 1
else
    echo "Firewall verification passed - unable to reach https://example.com as expected"
fi

# Verify Anthropic API access (critical for Claude to function)
if ! curl -4 --connect-timeout 5 https://api.anthropic.com >/dev/null 2>&1; then
    echo "WARNING: Unable to reach api.anthropic.com — Claude may not function correctly"
else
    echo "Firewall verification passed - able to reach api.anthropic.com as expected"
fi
