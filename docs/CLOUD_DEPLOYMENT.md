# Cloud Deployment Guide

This guide covers deploying Vitso Dev Orchestrator to various cloud providers. VDO is fully portable and can run on any platform that supports Docker.

## 🎯 Deployment Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Load Balancer                     │
└─────────────────────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
┌─────────▼────────┐            ┌────────▼─────────┐
│   Frontend       │            │   Backend API    │
│   (React App)    │            │   (FastAPI)      │
└──────────────────┘            └──────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
          ┌─────────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
          │   PostgreSQL     │  │     Redis      │  │   Workers      │
          │   (Managed DB)   │  │   (Cache)      │  │   (RQ)         │
          └──────────────────┘  └────────────────┘  └────────────────┘
```

## 📋 Pre-Deployment Checklist

- [ ] API keys for AI providers (Anthropic, OpenAI, Gemini)
- [ ] Cloud account with billing enabled
- [ ] Domain name (optional but recommended)
- [ ] SSL certificate (Let's Encrypt or cloud provider)
- [ ] Backup strategy decided

## 🚀 Quick Deploy Options

### Option 1: AWS (Recommended for Scale)

**Services Used:**
- ECS (Fargate) for containers
- RDS PostgreSQL for database
- ElastiCache Redis for queue
- Application Load Balancer
- ECR for Docker images
- S3 for backups

**Estimated Cost:** ~$50-150/month (t3.small instances)

### Option 2: Azure

**Services Used:**
- Azure Container Instances
- Azure Database for PostgreSQL
- Azure Cache for Redis
- Azure App Service
- Azure Container Registry

**Estimated Cost:** ~$60-180/month

### Option 3: DigitalOcean (Simplest)

**Services Used:**
- App Platform (managed containers)
- Managed PostgreSQL
- Managed Redis

**Estimated Cost:** ~$30-80/month

### Option 4: Railway/Render (Fastest)

**Services Used:**
- Managed containers
- Built-in PostgreSQL
- Built-in Redis

**Estimated Cost:** ~$20-50/month

---

## 🔧 Detailed Deployment Instructions

### AWS Deployment

#### Step 1: Prepare Infrastructure

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS
aws configure
```

#### Step 2: Create RDS Database

```bash
# Create PostgreSQL RDS instance
aws rds create-db-instance \
    --db-instance-identifier vitso-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15.3 \
    --master-username vitso \
    --master-user-password YOUR_SECURE_PASSWORD \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxxxxxxx \
    --db-name vitso_dev_orchestrator

# Wait for database to be available
aws rds wait db-instance-available --db-instance-identifier vitso-db

# Get endpoint
aws rds describe-db-instances \
    --db-instance-identifier vitso-db \
    --query 'DBInstances[0].Endpoint.Address'
```

#### Step 3: Create ElastiCache Redis

```bash
# Create Redis cluster
aws elasticache create-cache-cluster \
    --cache-cluster-id vitso-redis \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --num-cache-nodes 1

# Get endpoint
aws elasticache describe-cache-clusters \
    --cache-cluster-id vitso-redis \
    --show-cache-node-info
```

#### Step 4: Build and Push Docker Images

```bash
# Create ECR repositories
aws ecr create-repository --repository-name vitso/backend
aws ecr create-repository --repository-name vitso/frontend
aws ecr create-repository --repository-name vitso/worker

# Get login credentials
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t vitso/backend ./backend
docker tag vitso/backend:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/vitso/backend:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/vitso/backend:latest

docker build -t vitso/frontend ./frontend
docker tag vitso/frontend:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/vitso/frontend:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/vitso/frontend:latest

docker tag vitso/backend:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/vitso/worker:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/vitso/worker:latest
```

#### Step 5: Create ECS Cluster and Services

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name vitso-cluster

# Create task definitions (see aws/task-definitions/ folder)
# Deploy services (see aws/deploy.sh script)
```

#### Step 6: Configure Environment

```bash
# Create .env.production
cp backend/.env.cloud.template backend/.env.production

# Edit with your values
nano backend/.env.production
```

Example `.env.production` for AWS:

```env
DATABASE_URL=postgresql://vitso:password@vitso-db.xxxxx.us-east-1.rds.amazonaws.com:5432/vitso_dev_orchestrator
REDIS_HOST=vitso-redis.xxxxx.cache.amazonaws.com
REDIS_PORT=6379
ANTHROPIC_API_KEY=sk-ant-xxxxx
CLOUD_PROVIDER=aws
AWS_REGION=us-east-1
```

---

### DigitalOcean Deployment (Simplest Option)

#### Step 1: Install doctl CLI

```bash
# Install doctl
snap install doctl
# or
brew install doctl

# Authenticate
doctl auth init
```

#### Step 2: Create Managed Database

```bash
# Create PostgreSQL database
doctl databases create vitso-db \
    --engine pg \
    --region nyc1 \
    --size db-s-1vcpu-1gb \
    --version 15

# Create Redis database
doctl databases create vitso-redis \
    --engine redis \
    --region nyc1 \
    --size db-s-1vcpu-1gb
```

#### Step 3: Deploy to App Platform

```bash
# Create app.yaml configuration
cat > app.yaml << 'EOF'
name: vitso-dev-orchestrator
services:
- name: backend
  github:
    repo: your-username/vitso-dev-orchestrator
    branch: main
    deploy_on_push: true
  dockerfile_path: backend/Dockerfile
  http_port: 8000
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: DATABASE_URL
    scope: RUN_TIME
    value: ${db.DATABASE_URL}
  - key: REDIS_HOST
    scope: RUN_TIME
    value: ${redis.HOSTNAME}
  - key: ANTHROPIC_API_KEY
    scope: RUN_TIME
    type: SECRET
    value: your_key_here

- name: worker
  github:
    repo: your-username/vitso-dev-orchestrator
    branch: main
  dockerfile_path: backend/Dockerfile
  instance_count: 1
  instance_size_slug: basic-xxs
  run_command: rq worker vitso-jobs
  envs:
  - key: DATABASE_URL
    scope: RUN_TIME
    value: ${db.DATABASE_URL}

- name: frontend
  github:
    repo: your-username/vitso-dev-orchestrator
    branch: main
  dockerfile_path: frontend/Dockerfile
  http_port: 3000
  instance_count: 1
  instance_size_slug: basic-xxs
  routes:
  - path: /
EOF

# Deploy
doctl apps create --spec app.yaml
```

---

### Railway.app Deployment (Fastest Option)

#### Step 1: Install Railway CLI

```bash
npm install -g @railway/cli

# Login
railway login
```

#### Step 2: Initialize Project

```bash
cd vitso-dev-orchestrator

# Initialize
railway init

# Link to project
railway link
```

#### Step 3: Add Services

```bash
# Add PostgreSQL
railway add --database postgres

# Add Redis
railway add --database redis

# Deploy backend
cd backend
railway up

# Deploy frontend
cd ../frontend
railway up
```

#### Step 4: Configure Environment

```bash
# Set environment variables
railway variables set ANTHROPIC_API_KEY=your_key_here
railway variables set OPENAI_API_KEY=your_key_here
```

---

## 🔒 Production Security Checklist

- [ ] Use strong passwords for all services
- [ ] Enable SSL/TLS certificates
- [ ] Configure firewall rules
- [ ] Restrict database access to app servers only
- [ ] Use secrets management (AWS Secrets Manager, Azure Key Vault)
- [ ] Enable database encryption at rest
- [ ] Set up VPC/Virtual Network
- [ ] Enable logging and monitoring
- [ ] Configure automated backups
- [ ] Set up alerts for errors

---

## 📊 Monitoring and Observability

### CloudWatch (AWS)

```bash
# Enable container insights
aws ecs put-account-setting-default \
    --name containerInsights \
    --value enabled
```

### Application Monitoring

Add these to your deployment:

```python
# backend/main.py
from prometheus_client import make_asgi_app

# Add metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

---

## 💾 Backup Strategy

### Automated Database Backups

**AWS RDS:**
```bash
# Enable automated backups
aws rds modify-db-instance \
    --db-instance-identifier vitso-db \
    --backup-retention-period 7 \
    --preferred-backup-window "03:00-04:00"
```

**Manual Backup Script:**
```bash
# Create backup
./backup.sh

# Upload to S3
aws s3 cp backups/vdo_backup_*.tar.gz s3://your-backup-bucket/
```

---

## 🔄 Migration Between Cloud Providers

### Step 1: Backup Current Environment

```bash
./backup.sh
```

### Step 2: Deploy to New Provider

Follow deployment instructions for target provider

### Step 3: Restore Data

```bash
# On new machine
./restore.sh backups/vdo_backup_TIMESTAMP.tar.gz
```

### Step 4: Update DNS

Point your domain to new infrastructure

---

## 📈 Scaling Considerations

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
services:
  worker:
    deploy:
      replicas: 3  # Run 3 worker instances
      
  backend:
    deploy:
      replicas: 2  # Run 2 API instances
```

### Load Balancing

Use cloud provider's load balancer:
- AWS: Application Load Balancer
- Azure: Application Gateway
- DigitalOcean: Load Balancer

---

## 💰 Cost Optimization

### Development Environment
- Use smaller instance sizes
- Turn off during non-working hours
- Use spot/preemptible instances for workers

### Production Environment
- Reserved instances for predictable workloads
- Auto-scaling for variable loads
- CDN for frontend assets

**Estimated Monthly Costs:**

| Provider | Dev | Production |
|----------|-----|------------|
| AWS | $20-40 | $80-200 |
| Azure | $25-50 | $100-250 |
| DigitalOcean | $15-30 | $50-120 |
| Railway | $10-20 | $30-80 |

---

## 🆘 Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs backend
aws ecs describe-tasks --cluster vitso-cluster
```

### Database Connection Issues
```bash
# Test connection
docker run --rm postgres:15 psql $DATABASE_URL -c '\l'
```

### Memory Issues
```bash
# Increase container memory
# In docker-compose.yml:
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 📚 Additional Resources

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Azure Container Instances](https://docs.microsoft.com/azure/container-instances/)
- [DigitalOcean App Platform](https://docs.digitalocean.com/products/app-platform/)
- [Railway Documentation](https://docs.railway.app/)

---

## ✅ Post-Deployment Checklist

- [ ] Verify all services are running
- [ ] Test job submission and execution
- [ ] Configure automated backups
- [ ] Set up monitoring/alerts
- [ ] Document custom configuration
- [ ] Update DNS records
- [ ] Test disaster recovery procedure
- [ ] Review security settings
- [ ] Set up SSL certificates
- [ ] Configure CORS properly

---

**Next Steps:** See [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) for moving between environments.
