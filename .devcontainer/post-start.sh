#!/bin/bash
set -e

cd /workspace

# 1. Install pnpm dependencies (if package.json exists)
if [ -f package.json ]; then
    echo "Installing pnpm dependencies..."
    pnpm install
fi

# 2. Install Python package in development mode
echo "Installing Python package..."
uv sync --extra test

# 3. Configure firewall
echo "Configuring firewall..."
sudo /usr/local/bin/init-firewall.sh
