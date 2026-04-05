---
name: challenge-me
description: "Quick sanity check on your current approach. Spawns a fast Sonnet agent to challenge whether you're solving the right problem the right way. Use after building something, before committing to a direction, or when something feels off."
args:
  - name: target
    description: What to challenge — a file, plan, or recent work (optional)
    required: false
user-invocable: true
---

# Challenge Me

Fast approach validation. Gather context, spawn a Sonnet agent to poke holes, report back.

## Rules

- **Sonnet model only** — spawn the agent with `model: "sonnet"`. Fast and capable.
- **Pass all context inline** — the agent has no file access. Include intent, approach, and code directly in the prompt.
- **Return the agent response verbatim** — add nothing. The response is the deliverable.
- **Single agent, single round** — this is a quick gut-check, not a deep review. For thorough analysis, use `/codehealth` or `/devils-advocate`.

## Workflow

### Step 1: Gather Context

Collect two things:

1. **Intent** — what the user is trying to accomplish. Check (in order): the argument passed to the skill, recent conversation context, or ask: "What are you trying to achieve?"
2. **Approach** — what was built or proposed. Check: recent tool outputs in conversation (file writes, edits, plans), files the user points to, or ask: "What's your current approach?"

Read any referenced files to get the actual content. Summarize both intent and approach in 2-3 sentences each before spawning the agent.

### Step 2: Launch Agent

Use the agent template (`agent.md`). Replace placeholders:
- `{intent}` — the intent summary from Step 1
- `{approach}` — the approach summary from Step 1
- `{context}` — the actual code, plan, or output content (include file paths and line numbers when available)

Spawn with `model: "sonnet"`.

### Step 3: Report

Return the Sonnet agent's response directly to the user.
