# Article Session Handoff Prompt

Copy and paste everything below this line into a new conversation:

---

I'm editing Article 1 of a five-part series about securing AI-enabled development. I need you to help me finalize the article for LinkedIn publication.

## The Series

Five articles bridging the security-developer divide in the age of AI:

1. **"The Moment I Became the Developer I Was Trying to Protect"** ← Currently editing
2. "What Builders Can Do (That Makes Security's Job Possible)"
3. "What Security Can Do (That Doesn't Kill the Thing You're Protecting)"
4. "Getting Your Technology Teams on the Same Side of the Table"
5. "Zero Trust for AI Agents: A Technical Framework"

## My Background

I'm a CISSP-certified fractional CIO/CISO (not a developer) who built an AI-powered development platform (VDO) with Claude's help to understand AI-assisted development firsthand. In the process, I made every security mistake I'd normally audit others for. That lived experience is the foundation of this series.

## Article 1 Status

We have two versions:

**Main version:** `docs/ARTICLE-Zero-Trust-AI-Development.md`
- Solid content, all edits incorporated
- Reads well but paragraphs are denser

**Branch version:** Rendered as `Article-1-Branch-Punchy.md`
- Experimental rewrite with punchier rhythm
- Short paragraphs, impact lines get their own space
- More white space, lines like "Not once." and "Except later is always too late." stand alone
- Modeled after a style reference that used short declarative sentences and gut-punch endings

## Style Preferences

- No em dashes (use commas, periods, or parentheses instead)
- "Intoxicating" not "addictive" for describing velocity
- Avoid anything that sounds accusatory toward developers
- Impact statements should breathe (own line/paragraph)
- Thesis: "Velocity without boundaries is dangerous. But boundaries without velocity are useless."

## Key Frameworks

**Speed Limit Analogy:**
- School zone = 20, no exceptions
- Neighborhood = caution, stakes are real
- Highway = posts 65, we all drive 75 and check Waze
- Private track = no limit, you accept the risk

**Zone Model (for later articles):**
- Red Zone: PHI, production, customer data. Tightest controls.
- Yellow Zone: Pipeline. Validation, scanning, approval gates.
- Green Zone: Innovation. Freedom with visibility.

## Where We Left Off

I was comparing the main version vs. the punchy branch version to decide which rhythm works better, or if a blend is needed.

## Repository

`~/vitso-dev-orchestrator` (WSL Ubuntu)
- `docs/ARTICLE-SERIES-OUTLINE.md` - Full series outline
- `docs/ARTICLE-Zero-Trust-AI-Development.md` - Main draft
- `docs/TRANSITION-PROMPT-Articles.md` - Broader context prompt

Please read `docs/ARTICLE-Zero-Trust-AI-Development.md` and let me know you're oriented, then we can continue editing.
