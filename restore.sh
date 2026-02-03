#!/bin/bash

# Vitso Dev Orchestrator - Restore Script
# Restores a backup on a new machine

set -e

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_file.tar.gz>"
    echo ""
    echo "Available backups:"
    ls -lh backups/*.tar.gz 2>/dev/null || echo "  No backups found in ./backups/"
    exit 1
fi

BACKUP_FILE=$1
BACKUP_DIR="./backups"
TEMP_DIR="${BACKUP_DIR}/temp_restore"

echo "================================================"
echo "  Vitso Dev Orchestrator - Restore"
echo "================================================"
echo ""

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring from: $BACKUP_FILE"
echo ""

# Extract backup
echo "📦 Extracting backup..."
mkdir -p ${TEMP_DIR}
tar -xzf ${BACKUP_FILE} -C ${TEMP_DIR}

# Find the backup directory (it will be the only directory in temp)
BACKUP_NAME=$(ls ${TEMP_DIR})
RESTORE_PATH="${TEMP_DIR}/${BACKUP_NAME}"

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Services are running. Stopping them..."
    docker-compose down
fi

# Start only the database and redis services
echo "🚀 Starting database and Redis..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Restore database
if [ -f "${RESTORE_PATH}/database.sql" ]; then
    echo "📊 Restoring database..."
    docker-compose exec -T postgres psql -U vitso -d vitso_dev_orchestrator < ${RESTORE_PATH}/database.sql
    echo "✓ Database restored"
else
    echo "⚠️  No database backup found, creating fresh database..."
fi

# Restore Redis
if [ -f "${RESTORE_PATH}/redis.rdb" ]; then
    echo "💾 Restoring Redis data..."
    docker-compose stop redis
    docker cp ${RESTORE_PATH}/redis.rdb vitso-redis:/data/dump.rdb
    docker-compose start redis
    echo "✓ Redis data restored"
else
    echo "⚠️  No Redis backup found"
fi

# Restore configuration
if [ -f "${RESTORE_PATH}/.env" ]; then
    echo "⚙️  Restoring configuration..."
    cp ${RESTORE_PATH}/.env backend/.env
    echo "✓ Configuration restored"
    echo ""
    echo "⚠️  IMPORTANT: Review backend/.env and update API keys if needed!"
else
    echo "⚠️  No configuration backup found"
    echo "    You'll need to create backend/.env with your API keys"
fi

# Restore outputs
if [ -d "${RESTORE_PATH}/outputs" ]; then
    echo "📦 Restoring outputs..."
    mkdir -p backend/outputs
    cp -r ${RESTORE_PATH}/outputs/* backend/outputs/
    echo "✓ Outputs restored"
fi

# Clean up temp directory
echo "🧹 Cleaning up..."
rm -rf ${TEMP_DIR}

# Start all services
echo ""
echo "🚀 Starting all services..."
docker-compose up -d

echo ""
echo "================================================"
echo "  ✅ Restore Complete!"
echo "================================================"
echo ""
echo "Vitso Dev Orchestrator has been restored from backup."
echo ""
echo "📊 Dashboard: http://localhost:3000"
echo "🔧 API: http://localhost:8000"
echo ""
echo "⚠️  Remember to:"
echo "  1. Verify API keys in backend/.env"
echo "  2. Check service status: docker-compose ps"
echo "  3. View logs: docker-compose logs -f"
echo ""
