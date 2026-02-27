FROM debian:bookworm-slim

ARG TZ
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# Install system dependencies (no Node.js needed - Claude is a native binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  wget \
  less \
  git \
  procps \
  sudo \
  fzf \
  zsh \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iptables \
  ipset \
  iproute2 \
  dnsutils \
  aggregate \
  jq \
  nano \
  vim \
  rsync \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user (named 'node' for mount path compatibility)
ARG USERNAME=node
RUN useradd -m -s /bin/zsh -G sudo $USERNAME && \
    echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME

# Persist shell history
RUN mkdir /commandhistory && \
    touch /commandhistory/.bash_history && \
    chown -R $USERNAME /commandhistory

ENV DEVCONTAINER=true

# Create workspace and config directories
RUN mkdir -p /workspace /home/$USERNAME/.claude && \
    chown -R $USERNAME:$USERNAME /workspace /home/$USERNAME/.claude

WORKDIR /workspace

# Install git-delta
ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
    wget -q "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" -O /tmp/delta.deb && \
    dpkg -i /tmp/delta.deb && \
    rm /tmp/delta.deb

USER $USERNAME

# Shell setup
ENV SHELL=/bin/zsh
ENV EDITOR="nano"
ENV VISUAL="nano"

ARG ZSH_IN_DOCKER_VERSION=1.2.0
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
    -p git \
    -p fzf \
    -a "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
    -x

# Set up PATH for Claude binary
ENV PATH="/home/node/.local/bin:$PATH"

# Download Claude binary directly (native ELF, no Node.js needed)
RUN mkdir -p /home/$USERNAME/.local/bin && \
    ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64) PLATFORM="linux-x64" ;; \
      aarch64) PLATFORM="linux-arm64" ;; \
      *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    curl -fsSL "https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases/${CLAUDE_CODE_VERSION}/${PLATFORM}/claude" \
      -o /home/$USERNAME/.local/bin/claude && \
    chmod +x /home/$USERNAME/.local/bin/claude && \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/$USERNAME/.zshrc

# Disable auto-updates in ephemeral container
ENV DISABLE_AUTOUPDATER=1

# Copy and set up firewall script
COPY init-firewall.sh /usr/local/bin/
COPY entrypoint.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/init-firewall.sh /usr/local/bin/entrypoint.sh && \
    echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/$USERNAME-firewall && \
    chmod 0440 /etc/sudoers.d/$USERNAME-firewall
USER $USERNAME

LABEL claude.version="$CLAUDE_CODE_VERSION"
