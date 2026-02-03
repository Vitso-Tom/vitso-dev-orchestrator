#!/bin/bash
# Deploy Research Logs Schema to Job 53

# 1. Apply schema to the deployed SQLite database (if using SQLite)
# Or add to generated_files for VDO deployment

# Option A: Direct application to deployed instance
docker exec vitso-backend sqlite3 /mnt/demo-output/job-53/governance.db < /path/to/research_logs_schema.sql

# Option B: Add to VDO generated_files for redeployment
cd ~/vitso-dev-orchestrator

# Insert schema file
SCHEMA_CONTENT=$(cat research_logs_schema.sql | sed "s/'/''/g")
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "
INSERT INTO generated_files (job_id, filename, filepath, content, language, file_size) 
VALUES (53, 'research_logs_schema.sql', 'job_53/research_logs_schema.sql', 
'$SCHEMA_CONTENT', 'sql', $(wc -c < research_logs_schema.sql))
ON CONFLICT (job_id, filename) DO UPDATE SET content = EXCLUDED.content;"

# Insert research_agent.py
AGENT_CONTENT=$(cat research_agent.py | sed "s/'/''/g")
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "
INSERT INTO generated_files (job_id, filename, filepath, content, language, file_size) 
VALUES (53, 'research_agent.py', 'job_53/research_agent.py', 
'$AGENT_CONTENT', 'python', $(wc -c < research_agent.py))
ON CONFLICT (job_id, filename) DO UPDATE SET content = EXCLUDED.content;"

# Insert research_routes.py
ROUTES_CONTENT=$(cat research_routes.py | sed "s/'/''/g")
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "
INSERT INTO generated_files (job_id, filename, filepath, content, language, file_size) 
VALUES (53, 'research_routes.py', 'job_53/research_routes.py', 
'$ROUTES_CONTENT', 'python', $(wc -c < research_routes.py))
ON CONFLICT (job_id, filename) DO UPDATE SET content = EXCLUDED.content;"

# 2. Redeploy
curl -X POST http://localhost:8000/api/jobs/53/deploy

# 3. Verify deployment
docker exec vitso-backend ls -la /mnt/demo-output/job-53/*.py /mnt/demo-output/job-53/*.sql

echo "Done! Research logs schema and modules deployed."
