# Vitso Dev Orchestrator (VDO)

**AI-Powered Development Pipeline**

Vitso Dev Orchestrator is a full-stack autonomous development platform that queues jobs, plans execution, builds code, runs tests, and deploys to sandboxed environments - all monitored through a real-time dashboard.

## 🎯 What It Does

- **Queue Management**: Submit development jobs and VDO handles the rest
- **AI Planning**: Automatically breaks down tasks into executable phases
- **Multi-AI Orchestration**: Routes tasks to Claude, GPT-4, or Gemini based on task type
- **Automated Building**: AI writes and refines code iteratively
- **Test Automation**: Generates and runs tests automatically
- **Docker Sandboxing**: Tests code in isolated environments
- **Real-Time Monitoring**: Watch everything happen live in the dashboard

## 🏗️ Architecture

```
Frontend (React + Tailwind)
         ↓
FastAPI Backend (REST + WebSocket)
         ↓
Redis Job Queue → RQ Workers
         ↓
AI Orchestrator (Claude/GPT-4/Gemini)
         ↓
Docker Sandboxes
```

## 🚀 Quick Start

### Prerequisites

- Docker Desktop installed and running
- API keys for at least one AI provider (Claude recommended)

### Installation

```bash
# Clone or navigate to the project
cd vitso-dev-orchestrator

# Run the setup script
./setup.sh
```

The setup script will:
1. Check prerequisites
2. Create environment configuration
3. Build Docker containers
4. Start all services

### Configuration

Edit `backend/.env` and add your API keys:

```env
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here  # Optional
GOOGLE_API_KEY=your_google_key_here   # Optional
```

### Access

- **Dashboard**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 📖 How to Use

### Creating a Job

1. Click "New Job" in the dashboard
2. Enter a title and detailed description
3. Click "Create & Start"
4. Watch it execute in real-time!

### Example Job Descriptions

```
"Create a Python FastAPI application that processes CSV files and 
generates summary statistics with visualization charts"

"Build a React component for a user authentication flow with 
email/password login and JWT token management"

"Create a bash script that monitors system resources and sends 
alerts when thresholds are exceeded"
```

## 🛠️ Development

### Project Structure

```
vitso-dev-orchestrator/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models
│   ├── orchestrator.py      # AI routing logic
│   ├── worker.py            # Job processing
│   ├── database.py          # DB configuration
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # Main dashboard
│   │   ├── main.jsx        # Entry point
│   │   └── index.css       # Styles
│   └── package.json        # Node dependencies
├── docker-compose.yml       # Service orchestration
└── setup.sh                # Automated setup
```

### Running Without Docker

**Backend:**
```bash
cd backend
pip install -r requirements.txt
cp .env.template .env  # Add your API keys
python -m uvicorn main:app --reload

# In another terminal, start Redis and worker
redis-server
rq worker vitso-jobs
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 🎛️ System Components

### Backend Services

- **FastAPI Server** (Port 8000): REST API and WebSocket server
- **RQ Worker**: Processes jobs from the queue
- **PostgreSQL**: Stores jobs, tasks, and logs
- **Redis**: Job queue management

### AI Orchestrator

Smart routing system that selects the best AI for each task:

- **Planning**: Claude (excels at structured thinking)
- **Building**: Claude Code (great for code generation)
- **Testing**: GPT-4 (good at test generation)
- **Review**: Gemini (code review and analysis)

### Job Pipeline

1. **Queue**: Job submitted and queued
2. **Planning**: AI creates execution plan
3. **Building**: AI writes code
4. **Testing**: Automated tests run
5. **Sandboxing**: Deploy to Docker container
6. **Complete**: Ready for review

## 📊 Dashboard Features

- **Live Status**: Real-time job status updates
- **Pipeline View**: Visual representation of job phases
- **Log Streaming**: Watch AI work in real-time
- **Statistics**: Track completed, failed, and running jobs
- **Job History**: Browse past jobs and their outputs

## 🔧 Useful Commands

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f worker

# Stop all services
docker-compose down

# Restart services
docker-compose restart

# Rebuild after code changes
docker-compose up -d --build

# Check service status
docker-compose ps

# Access database directly
docker-compose exec postgres psql -U vitso -d vitso_dev_orchestrator
```

## 🐛 Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker info

# Check logs
docker-compose logs

# Restart everything
docker-compose down
docker-compose up -d
```

### Frontend can't connect to backend
- Check that backend is running: http://localhost:8000
- Verify API keys are set in `backend/.env`
- Check browser console for errors

### Worker not processing jobs
```bash
# Check worker logs
docker-compose logs worker

# Ensure Redis is running
docker-compose ps redis

# Restart worker
docker-compose restart worker
```

### Database issues
```bash
# Reset database
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d
```

## 🚨 Known Limitations

- Jobs run sequentially (parallel execution coming soon)
- Sandbox timeout is 5 minutes
- SQLite default (switch to PostgreSQL for production)
- No job persistence across container restarts (with SQLite)

## 🔐 Security Notes

- Never commit `.env` files with real API keys
- Run behind a firewall in production
- Docker socket access is required for sandboxing
- Consider API rate limits for AI providers

## 📈 Roadmap

- [ ] Parallel job execution
- [ ] Job templates library
- [ ] Enhanced sandbox management
- [ ] Code version control integration
- [ ] Slack/email notifications
- [ ] Job scheduling (cron-style)
- [ ] Multi-user support with auth
- [ ] Cost tracking per job
- [ ] Export job results

## 💡 Tips

1. **Be Specific**: Detailed job descriptions get better results
2. **Start Small**: Test with simple jobs first
3. **Watch Logs**: The log stream shows what's happening
4. **Iterate**: Refine job descriptions based on results
5. **Use Templates**: Save successful job descriptions for reuse

## 🤝 Contributing

This is a personal project, but suggestions are welcome!

## 📝 License

Private project for Vitso consulting use.

---

**Built with**: FastAPI, React, PostgreSQL, Redis, Docker, Claude AI

**Author**: Tom (Vitso Tech)

**Version**: 1.0.0
