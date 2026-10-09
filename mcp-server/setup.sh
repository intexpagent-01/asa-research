#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_PATH="$SCRIPT_DIR/server.js"

echo "Pacific Development Intelligence — MCP Server Setup"
echo "===================================================="
echo ""

# Check Node.js
if ! command -v node &>/dev/null; then
  echo "Error: Node.js is not installed."
  echo "Install it from https://nodejs.org/ (v18+ required)"
  exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
  echo "Error: Node.js v18+ required (found v$(node -v))"
  exit 1
fi
echo "Node.js $(node -v) found."

# Install dependencies
echo "Installing dependencies..."
cd "$SCRIPT_DIR"
npm install --silent 2>&1
echo "Dependencies installed."

# Detect Claude Desktop config path
if [ "$(uname)" = "Darwin" ]; then
  CONFIG_DIR="$HOME/Library/Application Support/Claude"
  CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
elif [ "$(uname)" = "Linux" ]; then
  CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/Claude"
  CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
else
  echo ""
  echo "Could not detect OS. Add this to your Claude Desktop config manually:"
  echo ""
  echo '  "pacific-dev-intel": {'
  echo "    \"command\": \"node\","
  echo "    \"args\": [\"$SERVER_PATH\"]"
  echo '  }'
  exit 0
fi

echo ""
echo "Claude Desktop config: $CONFIG_FILE"

# Create config directory if needed
mkdir -p "$CONFIG_DIR"

# Read or create config
if [ -f "$CONFIG_FILE" ]; then
  EXISTING=$(cat "$CONFIG_FILE")
  if echo "$EXISTING" | grep -q "pacific-dev-intel"; then
    echo ""
    echo "Already configured! The 'pacific-dev-intel' server is in your config."
    echo "Restart Claude Desktop to pick up any changes."
    exit 0
  fi
else
  EXISTING='{}'
fi

# Build the new config entry using node for safe JSON manipulation
NEW_CONFIG=$(node -e "
  const config = JSON.parse(process.argv[1]);
  if (!config.mcpServers) config.mcpServers = {};
  config.mcpServers['pacific-dev-intel'] = {
    command: 'node',
    args: ['$SERVER_PATH']
  };
  console.log(JSON.stringify(config, null, 2));
" "$EXISTING")

echo "$NEW_CONFIG" > "$CONFIG_FILE"

echo ""
echo "Done! Configuration added to Claude Desktop."
echo ""
echo "Next steps:"
echo "  1. Restart Claude Desktop (quit and reopen)"
echo "  2. Start a conversation and ask about Pacific aid"
echo "     Try: 'What aid is flowing to Fiji right now?'"
echo ""
echo "Server path: $SERVER_PATH"
echo "Data directory: $(ls -d "$SCRIPT_DIR"/data 2>/dev/null && echo "$SCRIPT_DIR/data" || echo "$SCRIPT_DIR/../signal/data")"
