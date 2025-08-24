#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Installing claude-nogit...${NC}"

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is required but not installed${NC}"
    exit 1
fi

if ! command -v claude &> /dev/null; then
    echo -e "${YELLOW}Warning: Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code${NC}"
fi

# Create local bin directory
mkdir -p ~/.local/bin

# Download the script
echo -e "${YELLOW}Downloading claude-nogit...${NC}"
curl -fsSL https://raw.githubusercontent.com/tnfru/claude-nogit/main/claude-nogit -o ~/.local/bin/claude-nogit

# Make executable
chmod +x ~/.local/bin/claude-nogit

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "${YELLOW}Adding ~/.local/bin to PATH...${NC}"
    
    # Add to appropriate shell config
    if [[ "$SHELL" == */zsh ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        echo -e "${GREEN}Added to ~/.zshrc${NC}"
    elif [[ "$SHELL" == */bash ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        echo -e "${GREEN}Added to ~/.bashrc${NC}"
    fi
    
    echo -e "${YELLOW}Please restart your shell or run: export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

echo -e "${GREEN}✓ Installation complete!${NC}"
echo -e "${GREEN}Usage: claude-nogit [project-directory]${NC}"
echo -e "${YELLOW}Example: claude-nogit ~/my-project${NC}"