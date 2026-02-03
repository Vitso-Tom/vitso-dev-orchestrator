# VDO Demo - Quick Reference Card

**Perfect for keeping on second monitor during demos!**

---

## 🎬 **5-Minute Demo Script**

```
MINUTE 1: Setup & Introduction
├─ "Let me show you VDO - AI that builds software"
├─ Open VDO UI (localhost:3000)
└─ "I'll give it a task, we'll watch it work, then run what it built"

MINUTE 2: Create Job
├─ Click "New Job"
├─ Title: "System Monitor Dashboard"
├─ Paste description (see below)
├─ Click "Create Job"
└─ "Now watch VDO work..."

MINUTES 3-4: Watch Build (narrate)
├─ Planning: "Breaking requirements into tasks..."
├─ Building: "Generating Python backend, HTML frontend..."
├─ Testing: "Validating code structure..."
├─ GitHub: "Committing to repository..."
└─ Status: "Completed - 8 files, 342 lines"

MINUTE 4.5: Deploy
├─ Purple panel appears: "Deploy Locally"
├─ "Let's run it..." [Click "Deploy Now"]
├─ Watch progress: Files → Dependencies → Starting...
├─ 30 seconds later: "Application Running"
└─ "And it's live!" [Click "Open →"]

MINUTE 5: Show & Teardown
├─ Browser opens → System monitor running
├─ "Real-time CPU, memory graphs..."
├─ Open Chrome → CPU spikes → Graphs respond
├─ "Prompt to demo in 4 minutes"
├─ Back to VDO → [Click "Stop & Cleanup"]
└─ "Ready for next demo"
```

---

## 📋 **Job Description (Copy-Paste Ready)**

```
Build a real-time system monitoring dashboard with these requirements:

BACKEND (Python Flask):
- Use psutil to gather: CPU %, memory usage, disk usage, network I/O
- API endpoint /api/metrics that returns JSON
- Update every 2 seconds
- Include timestamps

FRONTEND (HTML/CSS/JS):
- Modern, professional design with dark theme
- Use Chart.js for live-updating line graphs
- Display 4 panels:
  * CPU Usage (line graph, last 30 readings)
  * Memory Usage (gauge showing used/total)
  * Disk Usage (bar chart by mount point)
  * Network I/O (upload/download rates)
- Auto-refresh every 2 seconds
- Smooth animations
- Responsive layout

Include requirements.txt with: flask, psutil, flask-cors
Make it visually appealing with gradients and modern styling.
```

---

## 🎯 **Demo Checkpoints**

**Before Demo:**
- [ ] VDO running (`docker compose ps`)
- [ ] UI accessible (localhost:3000)
- [ ] `/mnt/demo-output` exists and empty
- [ ] Browser tabs: VDO UI, blank tab for demo app
- [ ] This reference card visible on second monitor

**During Demo:**
- [ ] Job created successfully
- [ ] Narrated each phase naturally
- [ ] Deploy button appeared
- [ ] Clicked "Deploy Now" confidently
- [ ] Application opened in browser
- [ ] Showed real-time response
- [ ] Clean teardown completed

**After Demo:**
- [ ] Deploy button back (ready for next demo)
- [ ] No processes lingering (`ps aux | grep python`)
- [ ] Demo output cleaned (`ls /mnt/demo-output`)

---

## 🗣️ **Key Talking Points**

**While Creating Job:**
- "VDO orchestrates multiple AI models - Claude, GPT, Gemini"
- "It handles the complete lifecycle: plan, build, test, deploy"

**During Planning Phase:**
- "Watch it analyze requirements and create a structured plan"
- "Breaking this into Planning, Building, Testing phases"

**During Building Phase:**
- "AI is writing Flask backend, HTML frontend, installing Chart.js"
- "It's generating actual production-ready code"

**During GitHub Push:**
- "Everything's committed to GitHub automatically"
- "Complete audit trail, ready for team review"

**When Clicking Deploy:**
- "This is where it gets interesting..."
- "VDO will write files, install dependencies, start the server"
- "No manual commands - fully automated"

**When Showing Running App:**
- "From prompt to running application in 4 minutes"
- "Let me spike the CPU so you can see it respond..."
- [Open Chrome, watch graphs]
- "This is production-ready code, fully functional"

**During Teardown:**
- "One click cleanup - stops process, deletes files"
- "Ready for the next demo immediately"

---

## 🚨 **Emergency Responses**

**If deploy takes longer than expected:**
- "Sometimes dependencies take a bit longer..."
- "While we wait, let me show you the GitHub commit"
- [Show GitHub repo with generated files]

**If health check times out:**
- "Health check timeout, but application may still be running..."
- "Let me check manually"
- [Open browser to localhost:XXXX]
- Usually works fine

**If deployment fails:**
- "Let's check the logs to see what happened"
- [Click deployment logs]
- "This is actually a good learning moment..."
- [Explain the error, show how VDO helps debug]

**If something breaks completely:**
- "Let me show you a pre-built example instead..."
- [Have backup demo ready]
- OR: "This demonstrates the importance of testing..."
- [Pivot to discussion about CI/CD]

---

## 💡 **Demo Enhancements**

**Make it Interactive:**
- Ask audience: "What should we monitor?"
- Let someone suggest CPU/memory/disk
- "Great idea, let me add that to the prompt"

**Show the AI Working:**
- Point to task descriptions as they appear
- "See how it's generating specific functions?"
- "Now it's creating the Chart.js integration"

**Highlight Speed:**
- Start a timer on phone
- "Let's time this..."
- Show final time: "3 minutes 47 seconds"

**Compare to Manual:**
- "This would typically take a developer 2-4 hours"
- "We just did it in under 4 minutes"
- "And it includes tests, documentation, deployment"

---

## 🎨 **Visual Cues**

**Status Colors:**
- 🟡 Queued - Yellow
- 🔵 Planning - Blue
- 🟣 Building - Purple
- 🟢 Testing - Green
- ✅ Completed - Green checkmark

**Deployment Colors:**
- 🟣 Deploy prompt - Purple gradient
- 🔴 Deploying - Pink/red gradient
- 🔵 Running - Blue gradient
- ⚠️ Error - Orange gradient

**What to Point At:**
- Task list updating in real-time
- Status changing from phase to phase
- Deploy button appearing
- URL becoming clickable
- Graphs moving in real-time

---

## 📱 **Backup Plans**

**Plan A: Live Demo**
- Create job live
- Watch build
- Deploy and show
- Full 5-minute experience

**Plan B: Speed Run**
- Use pre-completed job
- Just show deploy → running
- 2-minute version

**Plan C: Recording**
- Have screen recording ready
- Show recording if tech fails
- Walk through recorded demo

**Plan D: Static Demo**
- Pre-deployed app running
- "Here's what VDO built earlier..."
- Show GitHub commits
- Walk through code

---

## 🔧 **Technical Details (If Asked)**

**"How does the AI know what to build?"**
- "We use a structured prompt with requirements"
- "VDO creates a plan first, then executes it"
- "Each phase uses the best AI model for that task"

**"What about security?"**
- "Great question! We actually just completed a security audit"
- "18 vulnerabilities found, categorized by severity"
- "We're implementing authentication, secrets management"
- [Can pivot to security discussion]

**"Does it work with existing codebases?"**
- "Yes! VDO has a codebase scanner"
- "It analyzes your project structure"
- "Generates tasks that reference actual files"
- [Can show Phase B1 features]

**"What AI models does it use?"**
- "Claude for planning and building"
- "OpenAI GPT for testing"
- "Gemini for code review"
- "Automatically routes to best model for each task"

---

## 🎯 **Success Metrics**

**Great Demo = 3+ of these:**
- [ ] Audience asked questions
- [ ] Someone said "wow" or "impressive"
- [ ] Request for follow-up
- [ ] Request for access to VDO
- [ ] Discussion about use cases

**Excellent Demo = 5+ of these:**
- [ ] All of the above +
- [ ] Someone took notes
- [ ] Someone took a photo/video
- [ ] Request to see code
- [ ] Discussion about implementation
- [ ] Request for consultation

---

## 📞 **Post-Demo Follow-Up**

**Immediate (while audience is present):**
- "Want to see the generated code?"
- [Show GitHub repo]
- "Questions about how this works?"
- [Take questions]

**Within 24 Hours:**
- Send link to GitHub repo
- Share architecture diagram
- Offer consultation call

**Within 1 Week:**
- Follow up on specific questions
- Share article about "vibe coders"
- Discuss potential collaboration

---

## 🎓 **Learning Points to Emphasize**

1. **Speed**: 4 minutes vs. hours manually
2. **Quality**: Production-ready, not prototype
3. **Automation**: Zero manual deployment
4. **Repeatability**: Demo again immediately
5. **Transparency**: GitHub commits, full audit trail
6. **Flexibility**: Modify prompt, rebuild quickly

---

**Print this card and keep it visible during demos!**

**Last minute prep:**
1. Deep breath
2. Check VDO is running
3. Clear /mnt/demo-output
4. Open browser tabs
5. Start with confidence!

**Remember:** You built this. You know how it works. If something breaks, that's a learning opportunity. Every demo makes you better!

🚀 **You've got this!**
