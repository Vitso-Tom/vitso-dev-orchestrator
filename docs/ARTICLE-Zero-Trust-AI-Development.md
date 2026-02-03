# The Moment I Became the Developer I Was Trying to Protect

*By Tom [Last Name], CISSP | Fractional CIO/CISO*

---

I didn't set out to become a developer. I set out to understand them.

For years I've watched development teams move with a velocity that makes security people nervous. I've also watched security programs slow development down in ways that make developers avoid security entirely.

Everyone thinks they understand the tension. I thought I did too, until I crossed the line myself.

I set out to immerse myself in AI development to learn the process and explore the possible. I wanted to see how the tools work in an IDE and how things get built. So I built an AI-powered development platform. Not as a thought experiment, but as a deliberate attempt to understand what AI-assisted engineering actually feels like in the hands of a builder.

The platform orchestrates multiple AI models (Claude, GPT, Gemini) to plan, build, test, and deploy code automatically. In one session, I watched it scan its own codebase, generate context-aware tasks referencing specific files and functions, produce working code, and push it to GitHub. All from a single job description.

The entire flow took minutes.

I'm not a developer. But suddenly, I felt like one. And the feeling was intoxicating: *this is fast, this is powerful, this is how development is going to happen.*

I understood why builders push past process. I understood why they want fewer gates, fewer committees, fewer approvals. I understood why friction turns into workarounds, then shadow IT, then "we had no idea they were even using that."

And in that flow of building, security never crossed my mind. Not once. It wasn't until I sat back to admire what I'd built that I realized I hadn't considered it at all.

I stored API keys in places I shouldn't have. I gave the system more access than it needed. I skipped authentication because it slowed me down. I pushed code faster than I could evaluate it.

Then I put my CISO hat back on.

The platform held API keys for three AI providers. It had GitHub credentials with repo creation permissions. It could scan any codebase I pointed it at and send that code to external AI services. It had no authentication, no authorization model, no audit trail beyond application logs.

I wasn't hostile to security. I just didn't want to slow down. Security felt like it could wait until later.

Except later is always too late.

I had become the developer I was trying to protect.

---

## The Speed Limit Insight

That moment changed how I think about AI security. It helped me understand the real tension engineers live with every day. And it clarified something important.

Buying the fastest car on the market doesn't mean you'll arrive at top speed. There are laws, road conditions, school zones, and common sense. But that doesn't mean we all drive 25 mph everywhere, either.

We adjust speed based on context. A school zone demands 20, no exceptions. Any recklessness there is unacceptable. A neighborhood means caution because the stakes are real. The highway posts 65, but let's be honest: we all drive 75, check Waze for cops, and call it calculated risk. A private track has no limit. You accept the risk and there are no bystanders.

The mistake most security programs make is treating everything like a school zone. Every tool requires the same approval process. Every environment gets the same controls. Every request triggers the same risk assessment.

The result? Developers route around security entirely. Shadow IT flourishes. Personal API keys proliferate. And security leaders lose visibility into the very risks they were trying to manage.

Not because developers are reckless, but because the organization didn't give them a safe place to go fast.

Velocity without boundaries is dangerous. But boundaries without velocity are useless.

The answer isn't to block AI tools. You can't block your way out of this. Developers will route around you, tools will proliferate, and risk will increase, not decrease.

The answer is to design systems where speed and safety aren't opposites. Where context determines controls, not one-size-fits-all policies.

---

## What Comes Next

This experience didn't just change how I think about AI. It gave me a framework for addressing the tension. One that doesn't ask developers or security to compromise, but instead changes the structure of the conversation.

They're not incompatible goals. They're incompatible processes. We can fix that.

Over the next four articles, I'll share what I learned:

**For builders:** How to preserve velocity without triggering security escalations, and how to make security say "yes" faster.

**For security leaders:** How to stop treating every context like a school zone, and how to become velocity amplifiers instead of velocity dampers.

**For executives:** How to get your technology teams on the same side of the table, solving problems together instead of negotiating across a divide.

**For practitioners:** A technical framework for extending zero trust to AI agents, treating them as first-class principals with identity, authorization, and accountability.

The organizations that figure this out will ship faster, attract better talent, and (counterintuitively) have stronger security postures. Because their developers won't be routing around security. They'll be working within a system designed to say "yes" as often as possible, as safely as necessary.

---

*Tom [Last Name] is a CISSP-certified fractional CIO/CISO helping healthcare, SaaS, and AI-driven organizations navigate the intersection of security, innovation, and regulatory compliance.*
