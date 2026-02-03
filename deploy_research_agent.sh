#!/bin/bash
# Deploy Research Agent to VDO Job 53
# Run from ~/vitso-dev-orchestrator

set -e

echo "=== VDO Research Agent Deployment ==="
echo ""

# 1. Check if VDO containers are running
echo "[1/5] Checking VDO containers..."
if ! docker ps | grep -q vitso-backend; then
    echo "ERROR: vitso-backend container not running"
    echo "Run: cd ~/vitso-dev-orchestrator && docker-compose up -d"
    exit 1
fi
echo "✓ Containers running"

# 2. Apply database schema via PostgreSQL
echo ""
echo "[2/5] Applying research_logs schema to PostgreSQL..."
docker exec -i vitso-postgres psql -U vitso -d vitso_dev_orchestrator << 'EOF'
-- Research Logs Schema for AI Vendor Research Agent
-- PostgreSQL version for VDO

CREATE TABLE IF NOT EXISTS research_logs (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER,
    vendor_name VARCHAR(255) NOT NULL,
    product_name VARCHAR(255),
    research_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence_score DECIMAL(3,2),
    confidence_level VARCHAR(20),
    sources_consulted INTEGER DEFAULT 0,
    sources_cited INTEGER DEFAULT 0,
    facts_extracted INTEGER DEFAULT 0,
    facts_dropped INTEGER DEFAULT 0,
    gaps_identified JSONB,
    synthesis_model VARCHAR(100),
    synthesis_notes TEXT,
    synthesized_report TEXT,
    structured_data JSONB,
    status VARCHAR(20) DEFAULT 'completed',
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMP,
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_queries (
    id SERIAL PRIMARY KEY,
    research_log_id INTEGER NOT NULL REFERENCES research_logs(id) ON DELETE CASCADE,
    query_sequence INTEGER,
    query_type VARCHAR(50),
    query_text TEXT NOT NULL,
    query_purpose TEXT,
    results_count INTEGER DEFAULT 0,
    results_raw JSONB,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS research_facts (
    id SERIAL PRIMARY KEY,
    research_log_id INTEGER NOT NULL REFERENCES research_logs(id) ON DELETE CASCADE,
    research_query_id INTEGER REFERENCES research_queries(id) ON DELETE SET NULL,
    fact_category VARCHAR(100),
    fact_key VARCHAR(255),
    fact_value TEXT,
    fact_context TEXT,
    source_url TEXT,
    source_title TEXT,
    source_date DATE,
    source_snippet TEXT,
    status VARCHAR(20) DEFAULT 'extracted',
    drop_reason TEXT,
    fact_confidence DECIMAL(3,2),
    verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(255),
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_research_logs_vendor ON research_logs(vendor_name);
CREATE INDEX IF NOT EXISTS idx_research_logs_assessment ON research_logs(assessment_id);
CREATE INDEX IF NOT EXISTS idx_research_logs_timestamp ON research_logs(research_timestamp);
CREATE INDEX IF NOT EXISTS idx_research_queries_log ON research_queries(research_log_id);
CREATE INDEX IF NOT EXISTS idx_research_facts_log ON research_facts(research_log_id);
CREATE INDEX IF NOT EXISTS idx_research_facts_category ON research_facts(fact_category);
CREATE INDEX IF NOT EXISTS idx_research_facts_status ON research_facts(status);

-- Views
CREATE OR REPLACE VIEW v_dropped_facts AS
SELECT 
    rl.vendor_name,
    rl.product_name,
    rl.research_timestamp,
    rf.fact_category,
    rf.fact_key,
    rf.fact_value,
    rf.drop_reason,
    rf.source_url,
    rf.source_snippet
FROM research_facts rf
JOIN research_logs rl ON rf.research_log_id = rl.id
WHERE rf.status = 'dropped';

CREATE OR REPLACE VIEW v_research_confidence AS
SELECT 
    rl.id,
    rl.vendor_name,
    rl.product_name,
    rl.confidence_score,
    rl.sources_consulted,
    rl.sources_cited,
    rl.facts_extracted,
    rl.facts_dropped,
    ROUND((rl.sources_cited::FLOAT / NULLIF(rl.sources_consulted, 0) * 100)::NUMERIC, 1) as citation_rate,
    ROUND((rl.facts_dropped::FLOAT / NULLIF(rl.facts_extracted + rl.facts_dropped, 0) * 100)::NUMERIC, 1) as drop_rate,
    rl.gaps_identified,
    rl.research_timestamp
FROM research_logs rl;

\echo 'Schema applied successfully'
EOF
echo "✓ Schema applied"

# 3. Copy agent files (already mounted via volume, but verify)
echo ""
echo "[3/5] Verifying research agent files..."
ls -la backend/research_agent.py backend/audit_agent.py backend/research_routes.py backend/research_models.py 2>/dev/null || {
    echo "ERROR: Missing research agent files in backend/"
    exit 1
}
echo "✓ Files present"

# 4. Check if router is registered in main.py
echo ""
echo "[4/5] Checking router registration..."
if grep -q "research_router" backend/main.py; then
    echo "✓ Router already registered"
else
    echo "Adding router to main.py..."
    # Add import after other imports
    sed -i '/^from database import/a from research_routes import research_router' backend/main.py
    # Add router include after app creation
    sed -i '/^app = FastAPI/a app.include_router(research_router)' backend/main.py
    echo "✓ Router registered"
fi

# 5. Restart backend to pick up changes
echo ""
echo "[5/5] Restarting backend..."
docker compose restart backend
sleep 3
echo "✓ Backend restarted"

# Verify tables exist
echo ""
echo "=== Verification ==="
docker exec vitso-postgres psql -U vitso -d vitso_dev_orchestrator -c "\dt research_*" 2>/dev/null || echo "(checking tables...)"
echo ""

echo "=== Deployment Complete ==="
echo ""
echo "Test the endpoint:"
echo ""
echo "  curl -X POST http://localhost:8000/api/research-vendor \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"vendor_name\": \"Anthropic\", \"product_name\": \"Claude\"}'"
echo ""
echo "View research logs:"
echo "  curl http://localhost:8000/api/research-logs"
echo ""
echo "View dropped facts (the a16z fix):"
echo "  curl http://localhost:8000/api/research-logs/1/dropped"
echo ""
