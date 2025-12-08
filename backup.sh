#!/bin/bash

# Vitso Dev Orchestrator - Backup Script
# Creates a complete backup of the system for portability

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="vdo_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "================================================"
echo "  Vitso Dev Orchestrator - Backup"
echo "================================================"
echo ""

# Create backup directory
mkdir -p ${BACKUP_PATH}

echo "Creating backup: ${BACKUP_NAME}"
echo ""

# 1. Export database
echo "📊 Exporting database..."
docker-compose exec -T postgres pg_dump -U vitso vitso_dev_orchestrator > ${BACKUP_PATH}/database.sql
echo "✓ Database exported"

# 2. Export Redis data
echo "💾 Exporting Redis data..."
docker-compose exec -T redis redis-cli --rdb /data/dump.rdb SAVE > /dev/null 2>&1
docker cp vitso-redis:/data/dump.rdb ${BACKUP_PATH}/redis.rdb
echo "✓ Redis data exported"

# 3. Copy environment configuration
echo "⚙️  Copying configuration..."
cp backend/.env ${BACKUP_PATH}/.env 2>/dev/null || echo "No .env file found"
echo "✓ Configuration copied"

# 4. Copy any job outputs/artifacts
echo "📦 Copying job outputs..."
if [ -d "backend/outputs" ]; then
    cp -r backend/outputs ${BACKUP_PATH}/outputs
    echo "✓ Outputs copied"
else
    echo "! No outputs directory found"
fi

# 5. Create metadata file
echo "📝 Creating metadata..."
cat > ${BACKUP_PATH}/backup_info.json << EOF
{
  "backup_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "version": "1.0.0",
  "hostname": "$(hostname)",
  "docker_version": "$(docker --version)",
  "components": [
    "database",
    "redis",
    "configuration",
    "outputs"
  ]
}
EOF
echo "✓ Metadata created"

# 6. Create archive
echo ""
echo "📦 Creating portable archive..."
cd ${BACKUP_DIR}
tar -czf ${BACKUP_NAME}.tar.gz ${BACKUP_NAME}
rm -rf ${BACKUP_NAME}
cd ..

ARCHIVE_SIZE=$(du -h ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz | cut -f1)

echo ""
echo "================================================"
echo "  ✅ Backup Complete!"
echo "================================================"
echo ""
echo "Backup Archive: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
echo "Size: ${ARCHIVE_SIZE}"
echo ""
echo "To restore on another machine:"
echo "  1. Copy ${BACKUP_NAME}.tar.gz to new machine"
echo "  2. Run: ./restore.sh ${BACKUP_NAME}.tar.gz"
echo ""
echo "To deploy to cloud:"
echo "  See: docs/CLOUD_DEPLOYMENT.md"
echo ""
