# Commands Used - Session 2025-12-29

## Database Verification

```bash
# Check research tables exist
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "\dt research_*"

# Check recent research logs
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "
SELECT id, vendor_name, product_name, research_timestamp 
FROM research_logs 
ORDER BY id DESC 
LIMIT 5
"

# Query HIPAA/BAA facts from most recent research
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "
SELECT fact_key, fact_value, source_url 
FROM research_facts 
WHERE research_log_id = (SELECT MAX(id) FROM research_logs)
AND (fact_key ILIKE '%hipaa%' OR fact_key ILIKE '%baa%' OR fact_value ILIKE '%hipaa%' OR fact_value ILIKE '%baa%')
"

# Check generated_files for save_to_db setting
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "
SELECT substring(content from 'save_to_db[^,}]+') 
FROM generated_files 
WHERE job_id = 53 AND filename = 'app.py'
"
```

## Docker Container Status

```bash
# List all vitso containers
docker ps -a | grep vitso

# Check backend logs (follow)
docker logs -f vitso-backend

# Check backend logs (tail)
docker logs vitso-backend --tail 50

# Check processes in backend container
docker exec vitso-backend ps aux | grep -E "python|flask|gunicorn"

# Check flask process specifically
docker exec vitso-backend ps aux | grep flask

# Check file modification time
docker exec vitso-backend stat /mnt/demo-output/job-53/app.py | grep Modify
```

## API Testing

```bash
# Test research endpoint
curl -X POST http://localhost:8000/api/research-vendor \
  -H "Content-Type: application/json" \
  -d '{"vendor_name": "Anthropic", "product_name": "Claude"}'

# Test with Cursor
curl -X POST http://localhost:8000/api/research-vendor \
  -H "Content-Type: application/json" \
  -d '{"vendor_name": "Cursor", "product_name": "Cursor IDE"}'

# Check deployment status
curl http://localhost:8000/api/jobs/53/deployment

# Redeploy job 53 (if using VDO deployment)
curl -X POST http://localhost:8000/api/jobs/53/deploy
```

## AITGP (Job 53) Management

```bash
# Start AITGP Flask app (THE MAIN RESTART COMMAND)
docker compose -f ~/vitso-dev-orchestrator/docker-compose.yml exec -d backend bash -c "cd /mnt/demo-output/job-53 && flask run --host=0.0.0.0 --port=5050"

# Kill and restart (use with caution)
docker compose -f ~/vitso-dev-orchestrator/docker-compose.yml exec -d backend bash -c "pkill -f 'flask run.*5050'; sleep 2; cd /mnt/demo-output/job-53 && flask run --host=0.0.0.0 --port=5050"
```

## Code Inspection

```bash
# Search for research references in Job 53
docker exec vitso-backend grep -r "research" /mnt/demo-output/job-53/ --include="*.py" | head -30

# Check VDO_API_URL setting
docker exec vitso-backend grep -i "VDO_API" /mnt/demo-output/job-53/app.py | head -5

# Check call_vendor_research function
docker exec vitso-backend grep -A 10 "call_vendor_research" /mnt/demo-output/job-53/app.py | head -20

# Check full function definition
docker exec vitso-backend grep -A 20 "def call_vendor_research" /mnt/demo-output/job-53/app.py
```

## File Edits

```bash
# Fix save_to_db setting (change False to True)
docker exec vitso-backend sed -i 's/"save_to_db": False/"save_to_db": True/' /mnt/demo-output/job-53/app.py
```

## Browser Console Commands (JavaScript)

```javascript
// Get form data (if form element exists)
JSON.stringify(Object.fromEntries(new FormData(document.querySelector('form'))), null, 2)

// Get all input values (for React apps without form element)
const inputs = {};
document.querySelectorAll('input, select, textarea').forEach(el => {
  const name = el.name || el.id || el.placeholder || el.className;
  if (name && el.value) inputs[name] = el.value;
});
console.log(JSON.stringify(inputs, null, 2));

// Intercept fetch calls to see API payloads
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  console.log('REQUEST:', args[0], args[1]?.body ? JSON.parse(args[1].body) : '');
  return originalFetch(...args);
};
```

## Useful Diagnostic Patterns

```bash
# Check for errors in backend logs
docker logs vitso-backend 2>&1 | grep -i -E "(error|exception|research)" | tail -20

# Watch backend logs in real-time
docker logs -f vitso-backend

# Check if port 5050 is responding
curl -I http://localhost:5050

# Check if port 8000 (VDO API) is responding
curl http://localhost:8000/
```
