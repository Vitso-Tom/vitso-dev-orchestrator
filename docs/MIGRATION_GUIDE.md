# Migration Guide

Complete guide for moving Vitso Dev Orchestrator between machines and cloud providers.

## 📦 What Gets Migrated

- ✅ All jobs and their history
- ✅ Task definitions and results
- ✅ Complete log history
- ✅ Job queue state
- ✅ Configuration settings
- ✅ Generated outputs/artifacts
- ❌ Running containers (these restart fresh)
- ❌ API keys (you'll need to reconfigure)

## 🎯 Migration Scenarios

### 1. Local Machine → Local Machine
**Use Case:** Moving to a new development computer

### 2. Local → Cloud
**Use Case:** Taking to production

### 3. Cloud → Cloud
**Use Case:** Changing cloud providers

### 4. Cloud → Local
**Use Case:** Debugging or development

---

## 🚀 Quick Migration (5 Minutes)

### On Source Machine

```bash
cd vitso-dev-orchestrator

# Create backup
./backup.sh

# Copy the backup file to new machine
# The file will be in: backups/vdo_backup_TIMESTAMP.tar.gz
```

### On Target Machine

```bash
# 1. Get VDO code (clone repo or copy files)
git clone your-repo
# OR copy the entire vitso-dev-orchestrator directory

cd vitso-dev-orchestrator

# 2. Ensure Docker is running
docker info

# 3. Restore from backup
./restore.sh /path/to/vdo_backup_TIMESTAMP.tar.gz

# 4. Update API keys in backend/.env
nano backend/.env

# 5. Start services
docker-compose up -d

# Done! Access at http://localhost:3000
```

---

## 📋 Detailed Migration Steps

### Phase 1: Preparation

#### On Source Machine

1. **Stop new job submissions** (optional, prevents data loss)
   ```bash
   # You can continue to let jobs run, or stop accepting new ones
   docker-compose stop frontend
   ```

2. **Wait for running jobs to complete** (optional)
   ```bash
   # Check for running jobs
   docker-compose logs worker | grep "Processing"
   ```

3. **Create backup**
   ```bash
   ./backup.sh
   ```

4. **Verify backup was created**
   ```bash
   ls -lh backups/
   # You should see: vdo_backup_TIMESTAMP.tar.gz
   ```

5. **Test backup integrity** (optional but recommended)
   ```bash
   tar -tzf backups/vdo_backup_TIMESTAMP.tar.gz | head
   ```

---

### Phase 2: Transfer

#### Option A: Direct Transfer (Same Network)

```bash
# From source machine
scp backups/vdo_backup_*.tar.gz user@target-machine:/path/to/destination/
```

#### Option B: Cloud Storage

```bash
# Upload to S3
aws s3 cp backups/vdo_backup_*.tar.gz s3://your-bucket/

# Download on target
aws s3 cp s3://your-bucket/vdo_backup_*.tar.gz ./backups/
```

#### Option C: USB/External Drive

```bash
# Copy to external drive
cp backups/vdo_backup_*.tar.gz /mnt/usb-drive/
```

---

### Phase 3: Setup Target Machine

#### If VDO Not Installed Yet

```bash
# Copy entire project directory
# OR clone from git
git clone your-repo
cd vitso-dev-orchestrator

# Ensure prerequisites
docker --version
docker-compose --version
```

#### If Using Cloud Provider

Follow the cloud-specific setup from [CLOUD_DEPLOYMENT.md](./CLOUD_DEPLOYMENT.md)

---

### Phase 4: Restore

```bash
cd vitso-dev-orchestrator

# Place backup file in backups directory
mkdir -p backups
cp /path/to/vdo_backup_*.tar.gz backups/

# Run restore
./restore.sh backups/vdo_backup_TIMESTAMP.tar.gz
```

The restore script will:
1. Extract the backup
2. Stop any running services
3. Restore database
4. Restore Redis queue
5. Restore configuration
6. Restore outputs
7. Start all services

---

### Phase 5: Verification

```bash
# Check all services are running
docker-compose ps

# Should see:
# - vitso-postgres: Up
# - vitso-redis: Up
# - vitso-backend: Up
# - vitso-worker: Up
# - vitso-frontend: Up

# View logs
docker-compose logs -f

# Test API
curl http://localhost:8000/api/stats

# Test frontend
# Open browser to: http://localhost:3000
```

---

### Phase 6: Post-Migration Configuration

#### Update API Keys

```bash
nano backend/.env

# Ensure these are set:
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

#### Restart After Config Changes

```bash
docker-compose restart backend worker
```

#### Update URLs (if deploying to cloud)

```bash
# Update backend/.env
VITE_API_URL=https://api.yourdomain.com
CORS_ORIGINS=https://yourdomain.com

# Rebuild frontend
docker-compose up -d --build frontend
```

---

## 🔄 Specific Migration Scenarios

### Local WSL → Local WSL (New Machine)

```bash
# On old machine
./backup.sh
cp backups/vdo_backup_*.tar.gz /mnt/c/Users/YourName/Desktop/

# On new machine (in WSL)
cp /mnt/c/Users/YourName/Desktop/vdo_backup_*.tar.gz ~/
# ... then follow normal restore process
```

---

### Local → AWS

1. **Create AWS infrastructure first**
   ```bash
   # Follow: docs/CLOUD_DEPLOYMENT.md - AWS section
   ```

2. **Modify backup for cloud database**
   ```bash
   # Instead of using restore.sh, manually import:
   
   # Import database
   psql $AWS_RDS_URL < backup_path/database.sql
   
   # Deploy app code
   # Push to ECR and deploy to ECS
   ```

3. **Use cloud-specific restore**
   ```bash
   # See: scripts/restore-to-aws.sh
   ```

---

### AWS → DigitalOcean

1. **Create DigitalOcean infrastructure**

2. **Export from AWS**
   ```bash
   # Connect to AWS RDS
   pg_dump $AWS_RDS_URL > aws_export.sql
   
   # Export Redis (if needed)
   redis-cli -h AWS_ELASTICACHE_ENDPOINT --rdb dump.rdb
   ```

3. **Import to DigitalOcean**
   ```bash
   # Import to DO PostgreSQL
   psql $DO_DATABASE_URL < aws_export.sql
   
   # Import Redis
   redis-cli -h DO_REDIS_HOST --pipe < dump.rdb
   ```

4. **Deploy application**
   ```bash
   # Use DigitalOcean App Platform
   doctl apps create --spec app.yaml
   ```

---

## 🔍 Troubleshooting Migrations

### Backup File Corrupted

```bash
# Verify integrity
tar -tzf backup_file.tar.gz

# If corrupted, try repair
tar -xzf backup_file.tar.gz --ignore-command-error
```

### Database Version Mismatch

```bash
# Check versions
docker-compose exec postgres psql -U vitso -c 'SELECT version();'

# If mismatch, upgrade PostgreSQL first
# Then retry restore
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R $USER:$USER vitso-dev-orchestrator/

# Fix execute permissions
chmod +x *.sh
```

### Port Conflicts

```bash
# Check what's using ports
netstat -tulpn | grep :8000
netstat -tulpn | grep :3000

# Change ports in docker-compose.yml if needed
```

### Docker Socket Permission Denied

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Re-login or:
newgrp docker
```

---

## 📊 Migration Checklist

### Pre-Migration
- [ ] Verify backup completed successfully
- [ ] Test backup integrity
- [ ] Document current configuration
- [ ] Note all API keys
- [ ] Export any custom scripts/modifications
- [ ] Take screenshots of current working state

### During Migration
- [ ] Transfer backup file securely
- [ ] Verify file transfer completed
- [ ] Check target machine prerequisites
- [ ] Follow restore process step-by-step
- [ ] Monitor logs during restore

### Post-Migration
- [ ] Verify all services running
- [ ] Test API endpoints
- [ ] Test frontend loads
- [ ] Submit test job
- [ ] Check job logs
- [ ] Verify database data intact
- [ ] Test creating new jobs
- [ ] Update DNS (if applicable)
- [ ] Configure monitoring
- [ ] Set up automated backups
- [ ] Document new infrastructure

---

## 🚨 Rollback Procedure

If migration fails, you can rollback:

### On Source Machine (if still available)

```bash
# Services should still be running
docker-compose ps

# If stopped, restart
docker-compose up -d
```

### On Target Machine

```bash
# Stop failed migration
docker-compose down -v

# Clean up
rm -rf vitso-dev-orchestrator/

# Start fresh if needed
```

---

## 💾 Continuous Migration Strategy

For ongoing migrations or multi-environment setups:

### Strategy 1: Blue-Green Deployment

1. Keep old environment running (Blue)
2. Set up new environment (Green)
3. Migrate data
4. Switch traffic to Green
5. Keep Blue as backup for 24-48 hours

### Strategy 2: Database Replication

```bash
# Set up continuous replication
# PostgreSQL logical replication
# Redis replication

# Allows near-zero downtime migrations
```

---

## 📈 Migration Performance

Expected times for different backup sizes:

| Database Size | Backup Time | Transfer Time* | Restore Time |
|---------------|-------------|----------------|--------------|
| < 100 MB | 10-30 sec | 1-5 min | 30-60 sec |
| 100 MB - 1 GB | 1-3 min | 5-15 min | 2-5 min |
| 1-10 GB | 5-15 min | 15-60 min | 10-30 min |
| > 10 GB | 15+ min | 60+ min | 30+ min |

*Transfer times vary by connection speed

---

## 🔐 Security During Migration

- **Encrypt backups**: Use GPG encryption for sensitive data
  ```bash
  gpg --encrypt backup_file.tar.gz
  ```

- **Secure transfer**: Use SCP, SFTP, or encrypted cloud storage

- **Rotate keys**: Consider rotating API keys after migration

- **Audit logs**: Review who accessed what during migration

---

## 📞 Getting Help

If you encounter issues during migration:

1. Check the logs: `docker-compose logs`
2. Verify prerequisites are met
3. Review this guide step-by-step
4. Check [CLOUD_DEPLOYMENT.md](./CLOUD_DEPLOYMENT.md) for cloud-specific issues
5. Consult the main [README.md](../README.md)

---

**Remember:** Test migrations with non-production data first!
