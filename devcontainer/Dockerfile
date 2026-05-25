FROM debian:bookworm-slim

ARG TZ
ENV TZ="$TZ"

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
  python3 \
  jq \
  nano \
  vim \
  rsync \
  tmux \
  pipewire \
  sound-theme-freedesktop \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Docker CLI + Compose plugin (for --docker socket mount; daemon runs on host)
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin docker-compose-plugin && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user (named 'node' for mount path compatibility)
ARG USERNAME=node
RUN useradd -m -s /bin/zsh $USERNAME

# Persist shell history
RUN mkdir /commandhistory && \
    touch /commandhistory/.bash_history && \
    chown -R $USERNAME /commandhistory

ENV DEVCONTAINER=true

# Create workspace, config, and runtime directories
RUN mkdir -p /workspace /home/$USERNAME/.claude /run/user/1000 && \
    chown -R $USERNAME:$USERNAME /workspace /home/$USERNAME/.claude /run/user/1000

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

# Declared here (not earlier) so version bumps only rebuild this layer, not apt-get etc.
ARG CLAUDE_CODE_VERSION
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

# Install uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Disable auto-updates in ephemeral container
ENV DISABLE_AUTOUPDATER=1
ENV COLORTERM=truecolor
ENV TERM=xterm-256color

# Copy and set up firewall script
COPY init-firewall.sh /usr/local/bin/
COPY docker-proxy.py /usr/local/bin/
COPY entrypoint.sh /usr/local/bin/
COPY tmux.conf /etc/tmux.conf
USER root
RUN chmod +x /usr/local/bin/init-firewall.sh /usr/local/bin/docker-proxy.py /usr/local/bin/entrypoint.sh && \
    echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/init-firewall.sh" > /etc/sudoers.d/$USERNAME-firewall && \
    chmod 0440 /etc/sudoers.d/$USERNAME-firewall
USER $USERNAME

LABEL claude.version="$CLAUDE_CODE_VERSION"
