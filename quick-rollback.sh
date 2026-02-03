#!/bin/bash
#
# Quick Rollback Script
# Restores VDO from most recent backup
#
# Usage: ./quick-rollback.sh
#

set -e

BACKUP_DIR="$HOME/vdo-backups"

echo "=============================================="
echo "VDO Quick Rollback"
echo "=============================================="
echo ""

# Find most recent backup
LATEST_BACKUP=$(ls -t "${BACKUP_DIR}" 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backups found in ${BACKUP_DIR}"
    echo ""
    echo "Please run backup-before-deployment.sh first"
    exit 1
fi

BACKUP_PATH="${BACKUP_DIR}/${LATEST_BACKUP}"

echo "Found backup: ${LATEST_BACKUP}"
echo "Location: ${BACKUP_PATH}"
echo ""
echo "⚠️  WARNING: This will restore VDO to the backup state"
echo ""
read -p "Continue with rollback? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Rollback cancelled"
    exit 1
fi

echo ""
echo "🔄 Running restore script..."
echo ""

cd "${BACKUP_PATH}"
./RESTORE.sh

echo ""
echo "=============================================="
echo "✅ Rollback complete!"
echo "=============================================="
