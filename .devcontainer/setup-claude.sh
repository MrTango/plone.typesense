#!/bin/bash
set -euo pipefail

# --- Install Claude Code with retry logic ---
MAX_RETRIES=3
RETRY_DELAY=5

for attempt in $(seq 1 $MAX_RETRIES); do
    echo "Installing Claude Code (attempt $attempt/$MAX_RETRIES)..."
    if curl -fsSL https://claude.ai/install.sh | bash; then
        echo "Claude Code installed successfully."
        break
    fi
    if [ "$attempt" -eq "$MAX_RETRIES" ]; then
        echo "WARNING: Claude Code installation failed after $MAX_RETRIES attempts."
        echo "It will be retried on next container start."
        exit 0
    fi
    echo "Retrying in ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
done

# Ensure claude is on PATH for this script
export PATH="$HOME/.claude/bin:$PATH"

# --- Optional MCP setup (non-fatal) ---
if command -v claude &>/dev/null; then
    echo "Installing claude-lfr MCP server..."
    uv tool install claude-lfr-mcp || echo "WARNING: Failed to install claude-lfr-mcp"

    echo "Configuring claude-lfr MCP server..."
    claude mcp add claude-lfr -- claude-lfr-mcp || echo "WARNING: Failed to configure claude-lfr MCP"

    echo "Installing Chrome DevTools MCP server globally..."
    pnpm install -g chrome-devtools-mcp@latest || echo "WARNING: Failed to install chrome-devtools-mcp"

    echo "Configuring Chrome DevTools MCP server..."
    claude mcp add chrome-devtools -- chrome-devtools-mcp --headless --isolated --chrome-arg=--no-sandbox --chrome-arg=--disable-setuid-sandbox --chrome-arg=--disable-dev-shm-usage --chrome-arg=--disable-gpu || echo "WARNING: Failed to configure chrome-devtools MCP"

    echo "Enabling remote control for all sessions..."
    claude config set -g preferRemoteControl true || echo "WARNING: Failed to set remote control config"
fi

echo "Claude Code setup complete."
