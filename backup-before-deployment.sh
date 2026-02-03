#!/bin/bash
#
# VDO Pre-Deployment Backup Script
# Creates a complete backup before adding deployment feature
#
# Usage: ./backup-before-deployment.sh
#

set -e  # Exit on error

BACKUP_DIR="$HOME/vdo-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="pre-deployment-${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "=============================================="
echo "VDO Pre-Deployment Backup"
echo "=============================================="
echo ""
echo "Creating backup at: ${BACKUP_PATH}"
echo ""

# Create backup directory
mkdir -p "${BACKUP_PATH}"

# Stop VDO
echo "🛑 Stopping VDO..."
cd ~/vitso-dev-orchestrator
docker compose down

echo ""
echo "📦 Backing up files..."

# Backup database
if [ -f "backend/vitso_dev_orchestrator.db" ]; then
    echo "   ✅ Database"
    cp backend/vitso_dev_orchestrator.db "${BACKUP_PATH}/"
fi

# Backup backend code
echo "   ✅ Backend code"
mkdir -p "${BACKUP_PATH}/backend"
cp -r backend/*.py "${BACKUP_PATH}/backend/" 2>/dev/null || true
cp backend/requirements.txt "${BACKUP_PATH}/backend/" 2>/dev/null || true
cp backend/Dockerfile "${BACKUP_PATH}/backend/" 2>/dev/null || true

# Backup frontend code
echo "   ✅ Frontend code"
mkdir -p "${BACKUP_PATH}/frontend/src"
cp -r frontend/src/* "${BACKUP_PATH}/frontend/src/" 2>/dev/null || true
cp frontend/package.json "${BACKUP_PATH}/frontend/" 2>/dev/null || true

# Backup docker-compose
echo "   ✅ Docker configuration"
cp docker-compose.yml "${BACKUP_PATH}/"

# Backup environment files
echo "   ✅ Environment files"
cp .env "${BACKUP_PATH}/" 2>/dev/null || true
cp backend/.env "${BACKUP_PATH}/backend.env" 2>/dev/null || true

# Create restore script
cat > "${BACKUP_PATH}/RESTORE.sh" << 'EOF'
#!/bin/bash
#
# Restore VDO from this backup
#

set -e

echo "=============================================="
echo "VDO RESTORE FROM BACKUP"
echo "=============================================="
echo ""
echo "⚠️  WARNING: This will overwrite current VDO files!"
echo ""
read -p "Are you sure you want to restore? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Restore cancelled"
    exit 1
fi

cd ~/vitso-dev-orchestrator

echo ""
echo "🛑 Stopping current VDO..."
docker compose down

echo ""
echo "📦 Restoring files..."

# Restore database
if [ -f "vitso_dev_orchestrator.db" ]; then
    echo "   ✅ Database"
    cp vitso_dev_orchestrator.db backend/
fi

# Restore backend
echo "   ✅ Backend code"
cp -r backend/*.py ~/vitso-dev-orchestrator/backend/

# Restore frontend
echo "   ✅ Frontend code"
cp -r frontend/src/* ~/vitso-dev-orchestrator/frontend/src/

# Restore docker-compose
echo "   ✅ Docker configuration"
cp docker-compose.yml ~/vitso-dev-orchestrator/

# Restore environment
if [ -f ".env" ]; then
    echo "   ✅ Environment files"
    cp .env ~/vitso-dev-orchestrator/
fi
if [ -f "backend.env" ]; then
    cp backend.env ~/vitso-dev-orchestrator/backend/.env
fi

echo ""
echo "🔨 Rebuilding containers..."
docker compose build

echo ""
echo "🚀 Starting VDO..."
docker compose up -d

echo ""
echo "✅ Restore complete!"
echo ""
echo "Check status: docker compose ps"
echo "View logs: docker compose logs -f"
EOF

chmod +x "${BACKUP_PATH}/RESTORE.sh"

# Create backup manifest
cat > "${BACKUP_PATH}/MANIFEST.txt" << EOF
VDO Backup Manifest
===================

Backup Date: $(date)
Backup Name: ${BACKUP_NAME}
VDO Version: $(cat VERSION 2>/dev/null || echo "unknown")

Contents:
- Database: vitso_dev_orchestrator.db
- Backend code: backend/*.py
- Frontend code: frontend/src/*
- Docker config: docker-compose.yml
- Environment: .env, backend.env

To Restore:
cd ${BACKUP_PATH}
./RESTORE.sh

Location: ${BACKUP_PATH}
EOF

echo ""
echo "📄 Creating backup summary..."
cat "${BACKUP_PATH}/MANIFEST.txt"

echo ""
echo "✅ Backup complete!"
echo ""
echo "Backup location: ${BACKUP_PATH}"
echo ""
echo "To restore later:"
echo "  cd ${BACKUP_PATH}"
echo "  ./RESTORE.sh"
echo ""
echo "🚀 Restarting VDO..."
docker compose up -d

echo ""
echo "=============================================="
echo "✅ Backup complete and VDO restarted"
echo "=============================================="
echo ""
echo "You can now safely proceed with deployment feature installation."
echo ""
