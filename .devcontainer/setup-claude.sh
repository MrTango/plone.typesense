#!/bin/bash
set -euo pipefail

echo "Installing Claude Code (native)..."
curl -fsSL https://claude.ai/install.sh | bash

# Ensure claude is on PATH for this script
export PATH="$HOME/.claude/bin:$PATH"

echo "Installing Chrome DevTools MCP server globally..."
pnpm install -g chrome-devtools-mcp@latest

echo "Configuring Chrome DevTools MCP server..."
claude mcp add chrome-devtools -- chrome-devtools-mcp

echo "Enabling remote control for all sessions..."
claude config set -g preferRemoteControl true

echo "Claude Code setup complete."
