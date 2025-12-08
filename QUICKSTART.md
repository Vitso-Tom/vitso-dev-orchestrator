# 🚀 QUICK START - Get Running in 5 Minutes

## What You Have

I've built you a complete **Vitso Dev Orchestrator** - a dashboard-driven AI development platform just like your friend's system. Here's what it does:

✅ Web dashboard to submit jobs  
✅ Queue system with multiple workers  
✅ AI planning, building, testing, sandboxing  
✅ Real-time logs and status updates  
✅ Docker-based sandboxes  
✅ Multi-AI orchestration (Claude, GPT-4, Gemini)

## Step 1: Get Your API Key

You need at least one AI API key. Claude is recommended:

1. Go to: https://console.anthropic.com/
2. Create an API key
3. Save it somewhere (you'll need it in Step 3)

## Step 2: Navigate to Project

```bash
cd ~/vitso-dev-orchestrator
```

(Or wherever you want to put it on your Windows/WSL system)

## Step 3: Configure API Keys

```bash
# Copy the template
cp backend/.env.template backend/.env

# Edit it (use nano, vim, or VS Code)
nano backend/.env
```

Add your API key:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Save and exit (Ctrl+X, Y, Enter in nano)

## Step 4: Run Setup

```bash
# Make sure Docker Desktop is running first!

# Run the automated setup
./setup.sh
```

This will:
- Check Docker is running
- Build all containers
- Start all services
- Initialize the database

Takes about 2-3 minutes.

## Step 5: Open Dashboard

Open your browser to:
```
http://localhost:3000
```

You should see the Vitso Dev Orchestrator dashboard!

## Step 6: Create Your First Job

1. Click "New Job" button
2. Enter:
   - **Title**: "Test Job - Hello World"
   - **Description**: "Create a simple Python script that prints Hello World and the current date/time"
3. Click "Create & Start"
4. Watch it work in real-time!

## What's Running

- **Frontend**: http://localhost:3000 (React dashboard)
- **Backend API**: http://localhost:8000 (FastAPI)
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **PostgreSQL**: Port 5432 (database)
- **Redis**: Port 6379 (job queue)

## Useful Commands

```bash
# View logs (see what's happening)
docker-compose logs -f

# Stop everything
docker-compose down

# Start everything
docker-compose up -d

# Restart after making changes
docker-compose restart backend
docker-compose restart frontend
```

## Troubleshooting

### "Docker is not running"
→ Start Docker Desktop on Windows

### "Permission denied on setup.sh"
→ Run: `chmod +x setup.sh`

### "Can't connect to backend"
→ Check API key is set in `backend/.env`  
→ Run: `docker-compose logs backend`

### Frontend won't load
→ Make sure port 3000 isn't already in use  
→ Run: `docker-compose logs frontend`

## Next Steps

1. Try a real project: "Build a REST API for a todo list app"
2. Explore the logs to see how AI plans and builds
3. Check out README.md for full documentation
4. Customize the AI routing in `backend/orchestrator.py`

## File Structure

```
vitso-dev-orchestrator/
├── README.md              ← Full documentation
├── QUICKSTART.md          ← This file
├── setup.sh              ← Automated setup
├── docker-compose.yml    ← Service configuration
├── backend/              ← Python/FastAPI backend
│   ├── main.py          ← API routes
│   ├── orchestrator.py  ← AI routing
│   ├── worker.py        ← Job processing
│   └── models.py        ← Database models
└── frontend/            ← React dashboard
    └── src/
        └── App.jsx      ← Main UI component
```

## Questions?

1. Check the logs: `docker-compose logs`
2. Read README.md for detailed docs
3. Check API docs: http://localhost:8000/docs

## Tips for Good Results

✅ **Be specific** in job descriptions  
✅ **Include context** about what you want built  
✅ **Start simple** and build up complexity  
✅ **Watch the logs** to understand what's happening  

---

**You're all set!** You now have your own autonomous AI development platform running. 🎉
