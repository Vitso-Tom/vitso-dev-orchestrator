# VDO: AI-Powered Development for Your Team

## Executive Summary

**What it is:** VDO (Vitso Dev Orchestrator) is a self-hosted platform that lets your development team use AI to generate code — with visibility, control, and guardrails your organization needs.

**The problem it solves:** Your developers are already using AI tools (ChatGPT, Claude, Copilot). They're copying code into personal accounts, pasting proprietary logic into external services, and you have no visibility. VDO brings this activity in-house, under your control.

**The outcome:** Faster development velocity with audit trails, centralized credentials, and the ability to enforce policy on what code goes where.

---

## What VDO Does

Think of VDO as a **controlled gateway to AI coding assistance**.

A developer describes what they need:
> "Create an API endpoint that returns customer order history with pagination"

VDO then:
1. **Plans** the work — breaks it into logical tasks
2. **Builds** the code — using AI models (Claude, GPT-4, Gemini)
3. **Tests** — generates test cases for the code
4. **Delivers** — pushes completed code to a GitHub repository

The developer gets working code in minutes instead of hours. You get visibility into every job, every AI call, and every output.

---

## What Your Team Sees

### The Dashboard
A web interface where developers:
- Submit new jobs with plain English descriptions
- Watch progress in real-time (planning → building → testing → complete)
- View generated code before it goes anywhere
- Rate outputs (building institutional knowledge of what works)

### The Output
- Code files delivered to GitHub repositories
- Full audit log of what was requested and what was generated
- Token usage and cost tracking per job

---

## What You Control

| Control Point | What It Means |
|---------------|---------------|
| **Credentials** | AI API keys are centralized — developers never see them, can't copy them to personal accounts |
| **Visibility** | Every job logged: who requested it, what they asked for, what was generated |
| **Cost** | Token usage tracked per job — know exactly what AI is costing you |
| **Output destination** | Code goes to your GitHub organization, not personal repos |
| **Model selection** | Choose which AI providers are available (some orgs restrict to specific vendors) |
| **Codebase scanning** | Optional: VDO can scan existing code for context, making outputs more relevant — but you control which repos are scannable |

---

## What's Required to Set It Up

### Infrastructure (One-Time Setup)

**Option A: Managed Cloud (Simplest)**
- Account on Railway, Render, or similar PaaS
- 30-60 minutes setup time
- ~$20-50/month
- Your IT team or a consultant can do this in an afternoon

**Option B: Your Own Cloud (AWS/Azure)**
- Runs in your existing cloud environment
- 1-2 days setup by your platform/DevOps team
- ~$50-150/month depending on usage
- Full control, meets compliance requirements

**Option C: On-Premises**
- Runs on any server that can run Docker
- Complete air-gap possible if needed
- You manage everything

### Credentials Needed

| Credential | Purpose | Where to Get It |
|------------|---------|-----------------|
| Anthropic API Key | Claude AI access | console.anthropic.com |
| OpenAI API Key | GPT-4 access | platform.openai.com |
| Google API Key | Gemini access | aistudio.google.com |
| GitHub Token | Code delivery | github.com/settings/tokens |

**Cost of AI APIs:** Typical job uses $0.10-0.50 in API calls. A developer doing 10 jobs/day ≈ $50-150/month in AI costs.

### Integration Points

- **GitHub:** VDO pushes code to repositories in your GitHub organization
- **SSO (Optional):** Can integrate with your identity provider
- **Audit/SIEM (Optional):** Logs can export to your security tooling

---

## How Employees Use It

### Day-to-Day Workflow

1. **Developer has a task:** "I need to add a password reset endpoint"

2. **Developer opens VDO dashboard** (web browser, internal URL)

3. **Developer submits job:**
   - Title: "Password reset endpoint"
   - Description: "Create a /reset-password endpoint that accepts email, generates a token, and sends a reset link. Include rate limiting."
   - Clicks "Create Job"

4. **Developer watches progress** (1-3 minutes):
   - Planning: Breaking down the task
   - Building: Generating code files
   - Testing: Creating test cases
   - Complete: Code pushed to GitHub

5. **Developer reviews output:**
   - Opens the generated GitHub repo
   - Reviews code, makes adjustments
   - Merges into their feature branch

### What VDO Is Good For

| ✅ Use VDO For | Example |
|----------------|---------|
| New features | "Create a user profile API" |
| Utilities and scripts | "Write a script to migrate data from CSV to database" |
| Boilerplate code | "Generate CRUD endpoints for inventory management" |
| Test generation | "Write unit tests for the payment module" |
| Documentation | "Generate API documentation for our endpoints" |
| Prototypes | "Build a quick proof-of-concept for the new dashboard" |

### What VDO Is NOT For

| ❌ Don't Use VDO For | Why |
|----------------------|-----|
| Debugging production issues | Requires runtime context, logs, investigation |
| Refactoring existing code | Needs deep understanding of dependencies |
| Security-sensitive code | Requires human review and expertise |
| Performance optimization | Needs profiling, measurement, iteration |

---

## Security Considerations

### What Leaves Your Network

When a developer submits a job, VDO sends:
- The job description (what they typed)
- Optionally: scanned codebase context (if enabled)

This goes to external AI APIs (Anthropic, OpenAI, Google) unless you deploy local models.

### What Stays Internal

- Credentials (API keys never exposed to end users)
- Audit logs
- Generated code (goes to your GitHub, not external)

### Recommendations

| Data Context | Recommendation |
|--------------|----------------|
| Open source / non-sensitive projects | Enable full VDO features including codebase scanning |
| Internal tools, low sensitivity | Enable VDO, disable codebase scanning for repos with connection strings |
| Regulated data adjacent (healthcare, finance) | Deploy with local AI models or restrict to synthetic/sanitized codebases |
| Highly classified / air-gapped | On-premises deployment with local models only |

---

## ROI / Business Case

### Time Savings

| Task | Without VDO | With VDO | Savings |
|------|-------------|----------|---------|
| New API endpoint | 2-4 hours | 15-30 min + review | 70-80% |
| CRUD boilerplate | 1-2 hours | 5-10 min + review | 80-90% |
| Unit test generation | 1-2 hours | 10-15 min + review | 75-85% |
| Documentation | 30-60 min | 5-10 min + review | 70-80% |

### Cost Model

**For a 10-developer team:**
- VDO infrastructure: ~$50/month
- AI API usage (moderate): ~$500/month
- **Total: ~$550/month**

**Compared to:**
- Each developer saving 5 hours/week
- 50 hours/week × 4 weeks = 200 hours/month
- At $75/hour loaded cost = $15,000/month in developer time
- **ROI: 27x**

### Risk Reduction

- **Shadow IT eliminated:** Developers use the sanctioned tool, not personal accounts
- **Credential exposure reduced:** No API keys in developer hands
- **Audit trail established:** Every AI interaction logged
- **Code review maintained:** Output goes to GitHub, normal PR process applies

---

## Getting Started

### Phase 1: Pilot (Week 1-2)
- Deploy VDO to a test environment
- 2-3 developers trial it on non-critical projects
- Evaluate output quality and workflow fit

### Phase 2: Controlled Rollout (Week 3-4)
- Open to full development team
- Establish guidelines for appropriate use
- Monitor usage and costs

### Phase 3: Optimize (Ongoing)
- Refine which AI providers work best for your stack
- Enable/disable features based on data sensitivity
- Build library of high-quality reference jobs

---

## FAQ

**Q: Is the code VDO generates production-ready?**
A: It's first-draft quality. Developers should review, test, and refine before merging to production — same as any code, whether human or AI-generated.

**Q: Can we use our own AI models?**
A: Yes. VDO can be configured to use local/private AI deployments instead of external APIs.

**Q: What if a developer tries to paste sensitive data into a job description?**
A: VDO logs everything, so you'd have visibility. DLP integration is possible for automated detection. Training developers on appropriate use is recommended.

**Q: How is this different from GitHub Copilot?**
A: Copilot is inline code completion. VDO is job-based code generation — you describe a complete feature, it delivers complete files. They're complementary.

**Q: What happens if one AI provider has an outage?**
A: VDO supports multiple providers. If Claude is down, jobs can route to GPT-4 or Gemini automatically.

---

## Next Steps

1. **Technical evaluation:** Deploy VDO in a sandbox environment
2. **Security review:** Assess data flow against your policies
3. **Pilot program:** 2-3 developers, 2 weeks, non-sensitive projects
4. **Decision:** Roll out, adjust, or pass

---

*VDO is open source and available at github.com/Vitso-Tom/vitso-dev-orchestrator*

*For deployment assistance or enterprise features, contact [your info here]*
