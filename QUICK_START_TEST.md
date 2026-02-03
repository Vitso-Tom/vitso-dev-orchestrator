# Quick Start: Testing Fixes 13-14

## 1. Restart Services

```bash
# VDO Backend (picks up research_agent_v2.py changes)
cd ~/vitso-dev-orchestrator
docker compose restart backend worker

# AITGP Flask (picks up app.py Fix 13)
pkill -f "flask run"
cd ~/aitgp-app/job-53
python3 -m flask run --host=0.0.0.0 --port=5001 &
```

## 2. Clear Tabnine Cache (for clean test)

```bash
psql -d vdo -c "DELETE FROM vendor_facts WHERE vendor_name = 'Tabnine';"
psql -d vdo -c "DELETE FROM research_logs WHERE vendor_name = 'Tabnine';"
```

## 3. Run Test

1. Go to AITGP: http://localhost:5001
2. Enter: **Tabnine** 
3. Select: **PHI** in data types
4. Click: **Run Assessment**

## 4. Expected Results

| Check | Expected | Fix |
|-------|----------|-----|
| Recommendation | **CONDITIONAL NO-GO** (not GO) | Fix 13 |
| Condition text | "HIPAA BAA Unconfirmed" | Fix 13 |
| Primary source | `trust.tabnine.com` | Fix 14 |
| Source labels | "Vendor Source" vs "Third Party" | Fix 14 |
| No FedRAMP | Should not claim FedRAMP | Fix 14 |

## 5. If Issues

- Check VDO logs: `docker compose logs backend -f`
- Check Flask logs: visible in terminal
- Check PostgreSQL: `psql -d vdo -c "SELECT * FROM vendor_facts WHERE vendor_name = 'Tabnine' LIMIT 10;"`

## Files Changed

- `aitgp-app/job-53/app.py` - Fix 13 (BAA negation)
- `vitso-dev-orchestrator/backend/research_agent_v2.py` - Fix 14 (source hierarchy)
- `vitso-dev-orchestrator/backend/vendor_registry_seed.py` - Added Tabnine
