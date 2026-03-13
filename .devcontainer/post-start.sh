#!/bin/bash
set -e

cd /workspace

# 0. Ensure Claude Code is installed (fallback if postCreateCommand failed)
if ! command -v claude &>/dev/null; then
    echo "Claude Code not found, installing..."
    curl -fsSL https://claude.ai/install.sh | bash || echo "WARNING: Claude Code installation failed"
fi

# 1. Install pnpm dependencies (if package.json exists)
if [ -f package.json ]; then
    echo "Installing pnpm dependencies..."
    pnpm install
fi

# 2. Install Python package in development mode
echo "Installing Python package..."
uv sync --extra test

# 3. Pre-download embedding model for claude-lfr-mcp (before firewall blocks HuggingFace)
LFR_PYTHON="$HOME/.local/share/uv/tools/claude-lfr-mcp/bin/python"
if [ -x "$LFR_PYTHON" ]; then
    echo "Pre-downloading BAAI/bge-base-en-v1.5 embedding model..."
    "$LFR_PYTHON" -c "
from transformers import AutoTokenizer, AutoModel
AutoTokenizer.from_pretrained('BAAI/bge-base-en-v1.5')
AutoModel.from_pretrained('BAAI/bge-base-en-v1.5')
print('Embedding model downloaded successfully')
" || echo "WARNING: Failed to pre-download embedding model"
else
    echo "WARNING: claude-lfr-mcp not installed, skipping model download"
fi

# 4. Configure firewall
echo "Configuring firewall..."
sudo /usr/local/bin/init-firewall.sh
