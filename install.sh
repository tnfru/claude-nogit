#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

REPO_URL="https://raw.githubusercontent.com/tnfru/autobox/master"

echo -e "${GREEN}Installing autobox...${NC}"

# Check prerequisites
if ! command -v docker &>/dev/null; then
  echo -e "${RED}Error: Docker is required but not installed${NC}"
  exit 1
fi

if ! command -v claude &>/dev/null; then
  echo -e "${YELLOW}Warning: Claude CLI not found. Install with: curl -fsSL https://claude.ai/install.sh | bash${NC}"
fi

# Create local bin directory
mkdir -p ~/.local/bin

# Download the main script
echo -e "${YELLOW}Downloading autobox...${NC}"
curl -fsSL "$REPO_URL/autobox" -o ~/.local/bin/autobox
chmod +x ~/.local/bin/autobox

# Download devcontainer files
DEVCONTAINER_DIR="$HOME/.claude/devcontainer"
echo -e "${YELLOW}Setting up devcontainer files...${NC}"
mkdir -p "$DEVCONTAINER_DIR"
for file in Dockerfile entrypoint.sh init-firewall.sh docker-proxy.py; do
  curl -fsSL "$REPO_URL/devcontainer/$file" -o "$DEVCONTAINER_DIR/$file"
done
chmod +x "$DEVCONTAINER_DIR/entrypoint.sh" "$DEVCONTAINER_DIR/init-firewall.sh" "$DEVCONTAINER_DIR/docker-proxy.py"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo -e "${YELLOW}Adding ~/.local/bin to PATH...${NC}"

  if [[ "$SHELL" == */zsh ]] && ! grep -qF 'export PATH="$HOME/.local/bin' ~/.zshrc 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >>~/.zshrc
    echo -e "${GREEN}Added to ~/.zshrc${NC}"
  elif [[ "$SHELL" == */bash ]] && ! grep -qF 'export PATH="$HOME/.local/bin' ~/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >>~/.bashrc
    echo -e "${GREEN}Added to ~/.bashrc${NC}"
  fi

  echo -e "${YELLOW}Please restart your shell or run: export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

echo -e "${GREEN}✓ Installation complete!${NC}"
echo -e "${GREEN}Usage: autobox [project-directory]${NC}"
echo -e "${YELLOW}Example: autobox ~/my-project${NC}"
echo -e "${YELLOW}The network firewall is disabled by default; pass --firewall to restrict access.${NC}"
