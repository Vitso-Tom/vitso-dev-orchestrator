#!/bin/bash

# Vitso Dev Orchestrator - Restore Snapshot Script
# Restores source files from a snapshot

set -e

SNAPSHOT_DIR=".snapshots"

if [ -z "$1" ]; then
    echo "================================================"
    echo "  VDO Restore Snapshot"
    echo "================================================"
    echo ""
    echo "Usage: ./restore-snapshot.sh <snapshot_name>"
    echo ""
    echo "Available snapshots:"
    ls -1t "${SNAPSHOT_DIR}" 2>/dev/null | head -10 | sed 's/^/  /'
    exit 1
fi

SNAPSHOT_NAME="$1"
SNAPSHOT_PATH="${SNAPSHOT_DIR}/${SNAPSHOT_NAME}"

if [ ! -d "${SNAPSHOT_PATH}" ]; then
    echo "❌ Snapshot not found: ${SNAPSHOT_NAME}"
    echo ""
    echo "Available snapshots:"
    ls -1t "${SNAPSHOT_DIR}" 2>/dev/null | head -10 | sed 's/^/  /'
    exit 1
fi

echo "================================================"
echo "  VDO Restore Snapshot"
echo "================================================"
echo ""
echo "Restoring from: ${SNAPSHOT_NAME}"
echo ""

# Restore backend files
if [ -d "${SNAPSHOT_PATH}/backend" ]; then
    echo "📥 Restoring backend..."
    cp "${SNAPSHOT_PATH}/backend/"*.py backend/ 2>/dev/null || true
fi

# Restore frontend files
if [ -d "${SNAPSHOT_PATH}/frontend/src" ]; then
    echo "📥 Restoring frontend..."
    cp "${SNAPSHOT_PATH}/frontend/src/"*.jsx frontend/src/ 2>/dev/null || true
    cp "${SNAPSHOT_PATH}/frontend/src/components/"*.jsx frontend/src/components/ 2>/dev/null || true
fi

echo ""
echo "✅ Snapshot restored!"
echo ""
echo "You may need to restart containers:"
echo "  docker compose restart backend"
echo ""
