# VDO Portability Features

Vitso Dev Orchestrator is designed to be **fully portable** - you can move it between machines, operating systems, and cloud providers with ease.

## 🎯 Portability Philosophy

- **No vendor lock-in**: Works on any platform that supports Docker
- **Data independence**: All data stored in portable formats
- **Configuration externalized**: Environment-based config, not hardcoded
- **Stateless containers**: All state in volumes or external databases
- **Cloud-agnostic**: Same codebase works everywhere

## ✅ What Makes VDO Portable?

### 1. Containerization
Everything runs in Docker containers, which work identically across:
- Windows (via WSL or Docker Desktop)
- macOS
- Linux
- Cloud VM instances
- Kubernetes clusters

### 2. Volume Management
All persistent data stored in named volumes:
- `postgres_data`: Database
- `redis_data`: Queue state
- `backend_outputs`: Generated artifacts

### 3. Environment Configuration
No hardcoded values - everything in `.env`:
```env
DATABASE_URL=...
REDIS_HOST=...
ANTHROPIC_API_KEY=...
```

### 4. Automated Backup/Restore
One-command backup and restore:
```bash
./backup.sh    # Creates portable archive
./restore.sh   # Restores anywhere
```

---

## 🚀 Supported Platforms

### Local Development
- ✅ Windows 10/11 with WSL2
- ✅ Windows with Docker Desktop
- ✅ macOS (Intel & Apple Silicon)
- ✅ Linux (Ubuntu, Debian, RHEL, etc.)

### Cloud Providers
- ✅ AWS (ECS, EC2, Lightsail)
- ✅ Azure (Container Instances, VMs)
- ✅ Google Cloud (Cloud Run, Compute Engine)
- ✅ DigitalOcean (App Platform, Droplets)
- ✅ Railway
- ✅ Render
- ✅ Fly.io
- ✅ Any VPS with Docker

### Orchestration
- ✅ Docker Compose (default)
- ✅ Docker Swarm
- ✅ Kubernetes (with provided configs)
- ✅ Nomad

---

## 📦 Migration Scenarios

### Scenario 1: Development → Development
**Moving to a new laptop**

```bash
# Old machine
./backup.sh
scp backups/vdo_backup_*.tar.gz newlaptop:~/

# New machine
./restore.sh ~/vdo_backup_*.tar.gz
```

**Time:** 5-10 minutes

---

### Scenario 2: Local → Cloud
**Taking to production**

```bash
# Local
./backup.sh

# Cloud VM
./restore.sh backup.tar.gz
# Update .env with cloud database URLs
docker-compose up -d
```

**Time:** 15-30 minutes (including infrastructure setup)

---

### Scenario 3: Cloud → Cloud
**Changing providers (e.g., AWS → Azure)**

```bash
# AWS instance
./backup.sh
aws s3 cp backups/vdo_backup_*.tar.gz s3://bucket/

# Azure instance
az storage blob download --file backup.tar.gz --name vdo_backup_*.tar.gz
./restore.sh backup.tar.gz
```

**Time:** 20-40 minutes

---

### Scenario 4: Cloud → Local
**Bringing back for debugging**

```bash
# Download backup from cloud
./restore.sh backup.tar.gz
docker-compose -f docker-compose.cloud.yml --profile full up -d
```

**Time:** 10-15 minutes

---

## 🛠️ Portability Tools

### 1. Backup Script (`backup.sh`)

Creates a complete snapshot:
- Database dump (SQL format)
- Redis data (RDB format)
- Configuration files
- Job outputs
- Metadata

**Output:** Single `.tar.gz` file

**Usage:**
```bash
./backup.sh
# Creates: backups/vdo_backup_TIMESTAMP.tar.gz
```

---

### 2. Restore Script (`restore.sh`)

Restores from backup:
- Imports database
- Restores Redis
- Configures environment
- Starts services

**Usage:**
```bash
./restore.sh backups/vdo_backup_20250101_120000.tar.gz
```

---

### 3. Cloud Configurations

Multiple docker-compose files for different scenarios:

- `docker-compose.yml` - Local development (all services)
- `docker-compose.cloud.yml` - Cloud deployment (external DB/Redis)
- `docker-compose.prod.yml` - Production optimized

**Usage:**
```bash
# Local development
docker-compose up -d

# Cloud with managed services
docker-compose -f docker-compose.cloud.yml --profile app up -d
```

---

### 4. Environment Templates

Pre-configured templates for common scenarios:

- `.env.template` - Local development
- `.env.cloud.template` - Cloud deployment
- `.env.production.template` - Production hardening

---

## 📋 Portability Checklist

Before migrating, ensure you have:

- [ ] Current backup created (`./backup.sh`)
- [ ] Backup file verified (can extract)
- [ ] Target machine meets prerequisites
- [ ] Docker installed and running
- [ ] API keys documented
- [ ] Database credentials (if using external)
- [ ] Redis credentials (if using external)
- [ ] Firewall rules configured (if cloud)
- [ ] DNS records ready (if production)

---

## 🔒 Data Portability

### What's Included in Backups

✅ **Jobs Table**
- All job definitions
- Status and metadata
- Timestamps

✅ **Tasks Table**
- Task breakdowns
- Execution results
- Order and dependencies

✅ **Logs Table**
- Complete audit trail
- Timestamps and levels
- All messages

✅ **Queue State (Redis)**
- Pending jobs
- Worker state
- Scheduled tasks

✅ **Artifacts**
- Generated code
- Test results
- Build outputs

### What's NOT Included

❌ **Running Containers** (they restart fresh)
❌ **Docker Images** (rebuilt from Dockerfile)
❌ **API Keys** (reconfigured manually)
❌ **Temporary Files**
❌ **System Logs**

---

## 🌐 Cloud-Specific Notes

### AWS
- Use RDS for database (automatic backups)
- Use ElastiCache for Redis
- Store backups in S3
- Use ECR for Docker images

### Azure
- Use Azure Database for PostgreSQL
- Use Azure Cache for Redis
- Store backups in Blob Storage
- Use Container Registry

### DigitalOcean
- Use Managed PostgreSQL
- Use Managed Redis
- Store backups in Spaces
- Use Container Registry

### Railway/Render
- Built-in PostgreSQL (backed up automatically)
- Built-in Redis
- Platform handles backups

---

## 🔄 Continuous Portability

### Strategy 1: Regular Backups

```bash
# Add to crontab
0 2 * * * cd /path/to/vdo && ./backup.sh

# Or use systemd timer
# See: scripts/backup.timer
```

### Strategy 2: Version Control

```bash
# Keep configs in git
git add backend/.env.template
git add docker-compose*.yml
git commit -m "Updated configuration"
```

### Strategy 3: Infrastructure as Code

```bash
# Use Terraform for cloud infrastructure
terraform plan
terraform apply

# Or CloudFormation, Pulumi, etc.
```

---

## 💡 Best Practices

1. **Test Migrations Regularly**
   - Don't wait until you need to migrate
   - Practice with test data

2. **Document Custom Changes**
   - Keep notes of modifications
   - Update environment templates

3. **Version Your Backups**
   - Use timestamps
   - Keep multiple backups

4. **Separate Secrets**
   - Never commit .env files
   - Use secret management in production

5. **Use Managed Services in Production**
   - Let cloud provider handle database backups
   - Use managed Redis for persistence

6. **Test Restore Procedure**
   - Verify backups work before you need them
   - Practice disaster recovery

---

## 📊 Migration Time Estimates

| From | To | Setup Time | Data Transfer | Total |
|------|-----|-----------|---------------|-------|
| Local | Local | 5 min | 2 min | 7 min |
| Local | AWS | 30 min | 10 min | 40 min |
| AWS | Azure | 45 min | 20 min | 65 min |
| Any | Railway | 10 min | 5 min | 15 min |

*Times assume < 1GB database and good internet connection*

---

## 🎓 Learning Resources

- [Docker Volumes Documentation](https://docs.docker.com/storage/volumes/)
- [PostgreSQL Backup/Restore](https://www.postgresql.org/docs/current/backup.html)
- [Redis Persistence](https://redis.io/topics/persistence)
- [12-Factor App Principles](https://12factor.net/)

---

## 🆘 Troubleshooting Portability Issues

### "Database connection refused"
→ Check DATABASE_URL in .env
→ Ensure database is accessible from container network

### "Cannot find backup file"
→ Use absolute path: `./restore.sh /full/path/to/backup.tar.gz`

### "Permission denied"
→ Ensure scripts are executable: `chmod +x *.sh`

### "Volume mount failed"
→ Check Docker socket access
→ Verify volume paths exist

---

## ✅ Portability Verified

VDO has been tested on:
- Windows 11 WSL2 (Ubuntu 22.04)
- macOS Ventura (M1)
- Ubuntu 22.04 LTS
- AWS ECS (Fargate)
- DigitalOcean App Platform
- Railway

**Result:** Identical behavior across all platforms ✓

---

**Remember:** Portability is a feature that needs to be maintained. Always test migrations before you need them in production!
