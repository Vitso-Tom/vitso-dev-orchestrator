"""
Deployment API Endpoints

Add these endpoints to main.py to enable local deployment feature.
Append to the end of main.py before "if __name__ == '__main__':"
"""

# === DEPLOYMENT ENDPOINTS ===

@app.post("/api/jobs/{job_id}/deploy")
async def deploy_job_locally(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Deploy generated code locally for demo/testing.
    Starts deployment in background and returns immediately.
    """
    from deployment import deployment_manager
    
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    if job.deployment_pid:
        # Check if still running
        from deployment import deployment_manager as dm
        if dm.is_running(job_id):
            raise HTTPException(status_code=400, detail="Already deployed")
    
    # Mark as deployment requested
    job.deploy_local = True
    db.commit()
    
    # Start deployment in background
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
    
    # Check if process still running
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
    
    # Stop in background
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
