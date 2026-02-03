#!/bin/bash

# Vitso Dev Orchestrator - Code Snapshot Script
# Creates quick snapshots of source files for rollback during development

set -e

SNAPSHOT_DIR=".snapshots"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Optional: pass a label as argument
LABEL="${1:-snapshot}"
SNAPSHOT_NAME="${TIMESTAMP}_${LABEL}"
SNAPSHOT_PATH="${SNAPSHOT_DIR}/${SNAPSHOT_NAME}"

echo "================================================"
echo "  VDO Code Snapshot"
echo "================================================"
echo ""

# Create snapshot directory
mkdir -p "${SNAPSHOT_PATH}/backend"
mkdir -p "${SNAPSHOT_PATH}/frontend/src/components"

# Snapshot backend files
echo "📸 Snapshotting backend..."
cp backend/main.py "${SNAPSHOT_PATH}/backend/" 2>/dev/null || true
cp backend/models.py "${SNAPSHOT_PATH}/backend/" 2>/dev/null || true
cp backend/orchestrator.py "${SNAPSHOT_PATH}/backend/" 2>/dev/null || true
cp backend/worker.py "${SNAPSHOT_PATH}/backend/" 2>/dev/null || true

# Snapshot frontend files
echo "📸 Snapshotting frontend..."
cp frontend/src/App.jsx "${SNAPSHOT_PATH}/frontend/src/" 2>/dev/null || true
cp frontend/src/components/*.jsx "${SNAPSHOT_PATH}/frontend/src/components/" 2>/dev/null || true

# Create info file
cat > "${SNAPSHOT_PATH}/snapshot_info.txt" << EOF
Snapshot: ${SNAPSHOT_NAME}
Created: $(date)
Label: ${LABEL}

Files included:
$(find "${SNAPSHOT_PATH}" -type f -name "*.py" -o -name "*.jsx" | sed "s|${SNAPSHOT_PATH}/||")
EOF

echo ""
echo "✅ Snapshot created: ${SNAPSHOT_PATH}"
echo ""
echo "To restore: ./restore-snapshot.sh ${SNAPSHOT_NAME}"
echo ""

# List recent snapshots
echo "Recent snapshots:"
ls -1t "${SNAPSHOT_DIR}" 2>/dev/null | head -5 | sed 's/^/  /'
