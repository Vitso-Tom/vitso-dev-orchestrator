# Gamma Prompt: VDO Architecture Presentation

Create a 10-slide professional presentation about VDO (Vitso Dev Orchestrator), an AI-powered development pipeline.

## Slide 1: Title
**VDO: Vitso Dev Orchestrator**
Subtitle: AI-Powered Development Pipeline
Tagline: "Describe what you want, VDO builds it."

## Slide 2: The Problem
- Software development is slow and repetitive
- AI tools exist but require manual coordination
- No unified pipeline from idea to deployed code
- Developers spend time on boilerplate, not innovation

## Slide 3: The Solution
VDO automates the full development cycle:
- Takes a plain-English project description
- Automatically plans, builds, tests, and delivers code
- Pushes finished code directly to GitHub
- Real-time visibility into progress

## Slide 4: The 5-Phase Pipeline
Visual flow showing:
1. **Planning** → AI breaks down requirements into tasks (Claude)
2. **Building** → Code generated for each task (Claude)
3. **Testing** → Test cases written automatically (OpenAI)
4. **Sandboxing** → Code validated in isolated environment
5. **GitHub Push** → Delivered to repository automatically

## Slide 5: Multi-AI Orchestration
VDO routes tasks to the best AI for the job:
- **Claude** — Planning and code generation (best at reasoning)
- **OpenAI GPT-4** — Test generation (good at edge cases)
- **Gemini** — Code review (alternative perspective)

Not locked into one provider. Smart routing. Cost optimization.

## Slide 6: Architecture Overview
Visual diagram showing:
- Frontend (React) — Dashboard UI
- Backend (FastAPI) — API + WebSocket server
- Worker (RQ) — Job processing engine
- PostgreSQL — Data storage
- Redis — Queue + real-time pub/sub
- GitHub Integration — Code delivery

All containerized with Docker Compose.

## Slide 7: Real-Time Visibility
- WebSocket connection for instant updates
- Watch jobs progress through phases live
- Stream logs as they happen — no refresh needed
- See token usage and cost in real-time

## Slide 8: Key Features
- **Multi-AI Orchestration** — Best AI for each task
- **Real-time Dashboard** — Live progress and logs
- **Automatic GitHub Push** — Idea to repo, no manual steps
- **Token/Cost Tracking** — Full visibility into AI spend
- **Rating System** — Mark good outputs as reference examples
- **Self-improving** — VDO builds VDO improvements (dogfooding)

## Slide 9: Demo Snapshot
Show the dashboard with:
- Job list showing various statuses
- Selected job with pipeline progress
- Log panel with real-time entries
- GitHub repo link for completed job

Caption: "From description to deployed code in minutes"

## Slide 10: What's Next
Roadmap highlights:
- **Codebase Scanner** — VDO sees existing code, generates targeted edits
- **Edit Mode** — Modify existing files, not just create new ones
- **Verification Loop** — Actually run and validate generated code
- **Learning Loop** — Improve from corrections over time

---

## Style Notes for Gamma:
- Use a dark theme (slate/blue) to match the VDO dashboard aesthetic
- Include code snippets where relevant
- Use icons for the 5 phases (clipboard, hammer, test tube, box, GitHub logo)
- Keep text minimal, use visuals and diagrams
- Professional but modern tech startup feel
