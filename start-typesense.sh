#!/bin/bash
# Start Typesense for testing plone.typesense
#
# This script starts a Typesense server in Docker or Podman
# for running integration tests.

set -e

TYPESENSE_PORT=${TYPESENSE_PORT:-8108}
TYPESENSE_API_KEY=${TYPESENSE_API_KEY:-xyz}
TYPESENSE_DATA_DIR=${TYPESENSE_DATA_DIR:-/tmp/typesense-data}

# Detect container runtime
if command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
    VOLUME_OPTS="-v ${TYPESENSE_DATA_DIR}:/data"
elif command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
    # Add :z for SELinux contexts on Podman
    VOLUME_OPTS="-v ${TYPESENSE_DATA_DIR}:/data:z"
else
    echo "Error: Neither docker nor podman found."
    echo "Please install Docker or Podman to run Typesense."
    exit 1
fi

echo "========================================="
echo "Starting Typesense for plone.typesense"
echo "========================================="
echo ""
echo "Container runtime: $CONTAINER_CMD"
echo "Port:              $TYPESENSE_PORT"
echo "API Key:           $TYPESENSE_API_KEY"
echo "Data directory:    $TYPESENSE_DATA_DIR"
echo ""

# Create data directory if it doesn't exist
mkdir -p "$TYPESENSE_DATA_DIR"

# Check if Typesense is already running
if curl -s "http://localhost:${TYPESENSE_PORT}/health" &> /dev/null; then
    echo "⚠️  Typesense is already running on port ${TYPESENSE_PORT}"
    echo ""
    echo "To stop it, run:"
    echo "  ${CONTAINER_CMD} ps | grep typesense"
    echo "  ${CONTAINER_CMD} stop <container-id>"
    exit 0
fi

echo "Starting Typesense container..."
echo ""

$CONTAINER_CMD run \
    --name plone-typesense-test \
    --rm \
    -p "${TYPESENSE_PORT}:8108" \
    $VOLUME_OPTS \
    typesense/typesense:27.1 \
    --data-dir /data \
    --api-key="${TYPESENSE_API_KEY}"
