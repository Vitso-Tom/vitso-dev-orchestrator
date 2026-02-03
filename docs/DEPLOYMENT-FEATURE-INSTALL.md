# VDO Local Deployment Feature - Installation Guide

**Feature:** Automatic local deployment of generated code for demos and testing.

**Risk Level:** Low (non-breaking changes, full rollback support)

**Installation Time:** 15-20 minutes

---

## 🔒 **STEP 0: Backup (REQUIRED - Do This First!)**

```bash
cd ~/vitso-dev-orchestrator

# Make backup script executable
chmod +x backup-before-deployment.sh

# Run backup (takes 1-2 minutes)
./backup-before-deployment.sh
```

**What this does:**
- Stops VDO
- Backs up database, code, and config
- Creates restore script
- Restarts VDO
- Backup location: `~/vdo-backups/pre-deployment-YYYYMMDD_HHMMSS/`

**Rollback available:** If anything goes wrong, run `./quick-rollback.sh`

---

## 📦 **STEP 1: Install Dependencies**

```bash
cd ~/vitso-dev-orchestrator/backend

# Add httpx for health checks
echo "httpx==0.25.0" >> requirements.txt

# Stop VDO
cd ..
docker compose down

# Rebuild backend with new dependency
docker compose build backend worker

# Start VDO
docker compose up -d
```

---

## 🗄️ **STEP 2: Run Database Migration**

```bash
cd ~/vitso-dev-orchestrator/backend

# Run migration to add deployment fields
docker compose exec backend python migrations/add_deployment_fields.py
```

**Expected output:**
```
============================================
VDO Database Migration: Add Deployment Fields
============================================
🔄 Adding deployment fields to jobs table...
   ✅ Added deploy_local
   ✅ Added deployment_pid
   ✅ Added deployment_port
   ✅ Added deployment_url
   ✅ Added deployment_output_dir
   ✅ Added deployment_type
   ✅ Added deployment_error

✅ Migration completed successfully!
============================================
```

**If migration fails:** The script handles "already exists" errors gracefully. Safe to re-run.

---

## 🔌 **STEP 3: Add API Endpoints to main.py**

```bash
cd ~/vitso-dev-orchestrator/backend

# Backup current main.py
cp main.py main.py.backup

# Open main.py in editor
nano main.py
# OR
code main.py
```

**Add these lines at the very end, BEFORE `if __name__ == "__main__":`:**

```python
# ============================================================
# LOCAL DEPLOYMENT ENDPOINTS
# ============================================================

@app.post("/api/jobs/{job_id}/deploy")
async def deploy_job_locally(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Deploy generated code locally for demo/testing"""
    from deployment import deployment_manager
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    if job.deployment_pid:
        from deployment import deployment_manager as dm
        if dm.is_running(job_id):
            raise HTTPException(status_code=400, detail="Already deployed")
    
    job.deploy_local = True
    db.commit()
    
    background_tasks.add_task(deployment_manager.deploy, job_id)
    
    await manager.broadcast({
        "type": "deployment_started",
        "job_id": job_id
    })
    
    return {
        "message": "Deployment started",
        "job_id": job_id,
        "status": "deploying"
    }


@app.get("/api/jobs/{job_id}/deployment")
async def get_deployment_status(job_id: int, db: Session = Depends(get_db)):
    """Get current deployment status"""
    from deployment import deployment_manager
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    is_running = deployment_manager.is_running(job_id)
    
    return {
        "job_id": job_id,
        "deployed": is_running,
        "url": job.deployment_url if is_running else None,
        "port": job.deployment_port,
        "pid": job.deployment_pid,
        "output_dir": job.deployment_output_dir,
        "type": job.deployment_type,
        "error": job.deployment_error,
        "deploy_requested": job.deploy_local
    }


@app.delete("/api/jobs/{job_id}/deployment")
async def stop_deployment(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Stop deployment and cleanup files"""
    from deployment import deployment_manager
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    background_tasks.add_task(deployment_manager.stop, job_id)
    
    await manager.broadcast({
        "type": "deployment_stopped",
        "job_id": job_id
    })
    
    return {
        "message": "Deployment cleanup started",
        "job_id": job_id
    }


@app.get("/api/jobs/{job_id}/deployment/logs")
async def get_deployment_logs(
    job_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get deployment-related logs"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = db.query(Log).filter(
        Log.job_id == job_id,
        Log.message.contains('[DEPLOY]')
    ).order_by(Log.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "timestamp": log.timestamp.isoformat(),
            "message": log.message.replace('[DEPLOY] ', ''),
            "level": log.level
        }
        for log in logs
    ]
```

**Save and close the file.**

**Quick copy-paste option:** Use `deployment_endpoints.py` as reference

---

## 🎨 **STEP 4: Add Frontend Component**

The DeploymentPanel component is already created. Now integrate it:

```bash
cd ~/vitso-dev-orchestrator/frontend/src
```

**Edit your main job detail component (likely `App.jsx` or `JobDetail.jsx`):**

```javascript
// At the top with other imports:
import DeploymentPanel from './components/DeploymentPanel';

// Inside your job detail view, after job information:
{job.status === 'completed' && (
  <DeploymentPanel 
    jobId={job.id} 
    jobStatus={job.status} 
  />
)}
```

**Example integration in App.jsx:**

```javascript
// Find where job details are displayed (around line 200-300)
// Add DeploymentPanel after the generated files section:

<div className="job-section">
  <h3>Generated Files</h3>
  {/* ... existing generated files code ... */}
</div>

{/* ADD THIS: */}
<DeploymentPanel 
  jobId={selectedJob.id} 
  jobStatus={selectedJob.status} 
/>
```

---

## 🚀 **STEP 5: Restart VDO**

```bash
cd ~/vitso-dev-orchestrator

# Rebuild and restart everything
docker compose down
docker compose build
docker compose up -d

# Watch logs for any errors
docker compose logs -f --tail=50
```

**Expected output:**
```
vitso-backend  | ✓ Database initialized
vitso-worker   | ✓ Redis subscriber started
vitso-frontend | ➜  Local:   http://localhost:3000/
```

**Press Ctrl+C to stop watching logs**

---

## ✅ **STEP 6: Verify Installation**

### Test 1: API Endpoints

```bash
# Check backend is running
curl http://localhost:8000/

# Should return: {"name":"Vitso Dev Orchestrator",...}
```

### Test 2: Frontend UI

1. Open http://localhost:3000
2. Open a completed job
3. Scroll down - you should see the purple "Deploy Locally" panel

### Test 3: Full Deployment Flow

1. Create a simple job:
   - Title: "Hello World Server"
   - Description: "Create a simple Flask app that returns 'Hello World' on port 5000"

2. Wait for job to complete

3. Click "Deploy Now"

4. Wait ~30 seconds

5. Should show "Application Running" with clickable link

6. Click "Open →" - browser opens showing "Hello World"

7. Click "Stop & Cleanup"

8. Deployment panel resets to "Deploy Now" button

**If all tests pass:** ✅ Installation successful!

---

## 🔧 **Troubleshooting**

### Issue: Migration fails with "column already exists"

**Solution:** This is normal if re-running. The script handles it gracefully.

```bash
# Check if columns exist:
docker compose exec backend python -c "
from database import SessionLocal, engine
from sqlalchemy import inspect
inspector = inspect(engine)
columns = [col['name'] for col in inspector.get_columns('jobs')]
print('deployment_pid' in columns)  # Should print: True
"
```

### Issue: "Module 'deployment' not found"

**Solution:** Make sure `deployment.py` is in `/backend/` directory.

```bash
ls -la backend/deployment.py
# Should show: -rw-r--r-- ... deployment.py
```

### Issue: Deployment starts but health check fails

**Solution:** This is usually okay - app may need more startup time.

```bash
# Check deployment logs
curl http://localhost:8000/api/jobs/JOB_ID/deployment/logs

# Manually check if port is open
curl http://localhost:5050  # or whatever port was assigned
```

### Issue: "No available ports"

**Solution:** Free up ports 5050-5100 range.

```bash
# Find what's using ports
sudo lsof -i :5050-5100

# Kill processes if needed
sudo kill PID
```

### Issue: Frontend doesn't show DeploymentPanel

**Solution:** Check browser console for errors.

1. Open browser DevTools (F12)
2. Check Console tab for import errors
3. Verify DeploymentPanel.jsx and .css exist:

```bash
ls -la frontend/src/components/DeploymentPanel.*
```

---

## 🔙 **Rollback (If Needed)**

If anything goes wrong:

```bash
cd ~/vitso-dev-orchestrator

# Quick rollback to pre-deployment state
./quick-rollback.sh

# Follow prompts, confirm with "yes"
```

**This will:**
1. Stop VDO
2. Restore all files from backup
3. Rebuild containers
4. Start VDO

**Your VDO will be exactly as it was before installation.**

---

## 📊 **Post-Installation**

### Create Demo Output Directory

```bash
# Create persistent demo output directory
sudo mkdir -p /mnt/demo-output
sudo chown $USER:$USER /mnt/demo-output
chmod 755 /mnt/demo-output
```

### Update docker-compose.yml (Optional)

To persist demo files across container restarts:

```yaml
# Add to backend service:
backend:
  volumes:
    - ./backend:/app
    - /mnt/demo-output:/mnt/demo-output  # Add this line

# Add to worker service:
worker:
  volumes:
    - ./backend:/app
    - ./vdo_github:/vdo_github
    - /mnt/demo-output:/mnt/demo-output  # Add this line
```

Then restart:
```bash
docker compose down
docker compose up -d
```

---

## 🎯 **Next Steps**

1. **Test with simple jobs first:**
   - Flask Hello World
   - Static HTML page
   - Simple Python script

2. **Try the System Monitor demo:**
   - See `docs/DEMO-SCENARIOS.md` for full prompt

3. **Practice the demo flow:**
   - Create → Watch Build → Deploy → Show → Teardown
   - Should take 5-7 minutes total

4. **Customize as needed:**
   - Adjust port range in `deployment.py`
   - Modify UI colors in `DeploymentPanel.css`
   - Add custom deployment types

---

## 📝 **What Was Installed**

### Backend Files Created:
- `backend/deployment.py` - Deployment manager
- `backend/migrations/add_deployment_fields.py` - Database migration
- `backend/deployment_endpoints.py` - API endpoint reference

### Backend Files Modified:
- `backend/models.py` - Added 7 deployment fields to Job model
- `backend/main.py` - Added 4 deployment API endpoints
- `backend/requirements.txt` - Added httpx dependency

### Frontend Files Created:
- `frontend/src/components/DeploymentPanel.jsx` - React component
- `frontend/src/components/DeploymentPanel.css` - Styling

### Frontend Files Modified:
- `frontend/src/App.jsx` (or JobDetail.jsx) - Integrated DeploymentPanel

### Utility Scripts Created:
- `backup-before-deployment.sh` - Backup script
- `quick-rollback.sh` - Rollback script

---

## 🎓 **How It Works**

1. **User clicks "Deploy Now"**
   - POST to `/api/jobs/{id}/deploy`
   - Sets `deploy_local=true` flag
   - Starts background task

2. **DeploymentManager.deploy():**
   - Creates `/mnt/demo-output/job-{id}/`
   - Writes all generated files
   - Runs `pip install` or `npm install`
   - Finds available port (5050+)
   - Detects entry point (app.py, index.html, etc.)
   - Starts application
   - Health check (30 second timeout)

3. **UI polls every 2 seconds:**
   - GET `/api/jobs/{id}/deployment`
   - Updates deployment status
   - Shows URL when ready

4. **User clicks "Stop & Cleanup":**
   - DELETE `/api/jobs/{id}/deployment`
   - Kills process (SIGTERM, then SIGKILL)
   - Deletes output directory
   - Clears database fields

---

## ✅ **Success Criteria**

- [ ] Backup completed successfully
- [ ] Database migration ran without errors
- [ ] API endpoints added to main.py
- [ ] Frontend component integrated
- [ ] VDO starts without errors
- [ ] Can see "Deploy Now" button on completed jobs
- [ ] Can deploy a simple Flask app
- [ ] Application opens in browser
- [ ] Can stop and cleanup deployment
- [ ] Deploy button reappears after cleanup

**All checked?** 🎉 You're ready to demo!

---

## 📚 **Documentation**

- **Demo Scenarios:** See previous conversation for System Monitor demo
- **Architecture:** `backend/deployment.py` has detailed comments
- **API Reference:** `backend/deployment_endpoints.py`
- **Component Docs:** `frontend/src/components/DeploymentPanel.jsx`

---

**Questions or issues?** Check logs:
- Backend: `docker compose logs backend -f`
- Worker: `docker compose logs worker -f`
- Frontend: Browser DevTools Console

**Need help?** Review `quick-rollback.sh` - you can always restore!
