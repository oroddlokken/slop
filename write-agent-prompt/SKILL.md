---
name: write-agent-prompt
description: "Guidelines for authoring the text that defines a general agent — system prompts, personas, guardrails, tool descriptions, example sets. LLM-agnostic. Load when writing or editing the prose that steers an agent's behavior (persona, scope, clarification policy, output shape, uncertainty, escalation). For CLAUDE.md / AGENTS.md / coding-agent docs use write-agent-docs instead. For SDK wiring, prompt caching, and tool-use mechanics use claude-api."
---

# Writing Agent Prompts

Principles for the *text* that defines a production agent. LLM-agnostic. Sibling skills:
- `write-agent-docs` — CLAUDE.md / AGENTS.md for coding agents.
- `claude-api` — SDK wiring, caching, tool-use mechanics (the *how-to-call*, not the *what-to-say*).

## The Content Core

These principles transfer directly from agent-doc authoring; they apply to any prose an LLM reads as instruction.

### Framing: the Pink Elephant Effect
Positive directives outperform negative prohibitions. "NEVER discuss competitors" activates "competitors" in the model's attention — you just made the failure mode more available.

| Instead of | Write |
|---|---|
| "Never mention competitor products" | "Keep answers focused on our product line" |
| "Don't invent policy details" | "Quote the specific section you're citing, or say you're unsure" |
| "Don't be chatty" | "Answer in 1-3 sentences unless the user asks for more" |

Reserve NEVER/DO NOT for genuinely irreversible actions (PII disclosure, destructive tool calls). Every prohibition must also state what to do instead — a rule that only says "no" leaves the agent guessing.

### Reasoning Makes Rules Generalize
Rules with a "why" handle novel edge cases; rules without one break at the first surprise.

- Weak: "Use complete sentences."
- Strong: "TTS engines can't pronounce ellipses, markdown, or bullets, so use complete sentences in voice responses."

Faced with an emoji or a code block, the agent with the reasoning applies the principle. The agent with the bare rule flips a coin.

### Weak Language Dilutes Everything
- **Weak modals** — "should", "try to", "ideally", "prefer to". Rewrite as directives. If it's genuinely optional, say so and name the condition ("MAY ... when ...").
- **Weasel phrases** — "use appropriate tone", "as needed", "generally", "if relevant". Escape hatches. Replace with concrete conditions.
- **Unmeasurable quality** — "be helpful", "be friendly", "write naturally". The agent can't evaluate these. Make them checkable ("address the user by first name when known") or cut them.
- **Aggressive emphasis** — "YOU MUST", "CRITICAL", "NEVER EVER". Calm, direct instructions perform better on modern models. Reserve caps/bold for the 2-3 rules that actually matter; overuse dilutes all of them.

### Instruction Count vs. Compliance
Every rule you add weakens compliance with every other rule. Before adding rule N+1, look for one to delete. Compliance degrades roughly monotonically with length — there is no free rule. Formatting constraints hold up under load; semantic and compositional constraints break first — cut the fuzzy ones first.

In prompts past ~20 lines, put the rules you care most about at the **top or bottom**. The middle 40-60% is the lowest-attention zone in most current LLMs. In long-context deployments that fill more than half the window, earliest tokens can also lose salience — head-placement alone isn't a safety net.

### Avoid Redundancy
State each rule in one canonical section. Duplicated rules compete for the model's attention, and when one copy drifts during edits the inconsistency teaches the agent that rules are soft. If the same constraint applies to multiple sections, pick the most specific section and put it there; reference it from the others instead of copying.

### Cut What the Base Model Already Does
The single biggest quality issue in real system prompts is restating defaults: "be polite", "answer the user's question", "don't be offensive", "use proper grammar". All noise. If a rule would still be true with the word "not" inserted somewhere, it's not a rule — it's a platitude, and it dilutes the rules that carry information.

### Structure the Prompt
XML tags are the cross-vendor consensus for delimiting inputs, examples, and sections inside prompts. Anthropic trained Claude on XML; OpenAI's o3 guide recommends XML plus section headings; Google's Gemini docs concur. Reserve Markdown for prose narration; use XML tags for anything the model must parse or separate.

Good candidates for XML wrapping: user input (`<user_input>`), retrieved documents (`<document>`), few-shot examples (`<example>`), output schemas (`<output_schema>`), scratchpad space (`<thinking>`). Semantic names help — `<customer_email>` conveys more than `<text>`.

## Agent-Specific Content

These are the topics coding-agent docs don't cover and that general agents routinely fail at when unspecified.

### Persona — Operational, Not Emotional
"Be warm and helpful" is noise. What actually steers behavior:

- **Register** — "Match the formality of the user's last message" or "Always use full sentences; never reply with a single word."
- **Address** — first name, title, no name, inherit from session?
- **Sign-off** — close every message? never? only when resolving?
- **Self-reference** — "I", "we", or none?
- **Domain posture** — "Speak as a peer expert" vs. "Speak as a careful advisor who presents options." Different postures change what the agent offers unprompted (proposals vs. options) and how it phrases uncertainty.

Pick 4-6 concretely. Skip the adjectives.

### Scope Boundaries — Use a Scripted Redirect
State what the agent covers and what it refuses, *positively*, with the actual words:

- Covered: "Answer questions about <domain> using <sources>."
- Off-topic: "If asked about anything outside <domain>, reply with: '<exact redirect sentence>' and stop."

A scripted redirect sentence beats "refuse politely" — you get deterministic behavior and don't have to trust taste. Agents without a scripted sentence drift into apologetic rambling or helpful-sounding answers in categories you wanted them to refuse.

### Clarify, Proceed, or Assume-and-Proceed
The hardest problem in agent UX. A workable default:

1. **Proceed silently** if the request has one reasonable interpretation, or if being wrong is cheap and recoverable.
2. **Ask exactly one question** if the cost of being wrong is high *and* the ambiguity is narrow (binary, or a short enumerable list).
3. **State an assumption and proceed** if the ambiguity is open-ended: "I'll assume X unless you tell me otherwise." The user course-corrects without a round-trip.

Never ask more than one question at a time. Never ask a question whose answer is in the user's current message. Agents with no clarification policy default to asking three questions on every ambiguous input — a measurable UX failure.

### Output Shape
Specify the shape; the model will match it. Leave it vague and it drifts long and generic.

- **Length target** — "1-3 sentences", "under 100 words", "as long as the answer requires, no filler". Vague targets drift long every time.
- **Structure** — bullets, prose, table, or JSON. Pick one per response type.
- **Opening** — state the first thing the message should actually say. "Great question!", "I'd be happy to help", "Certainly!" are a signal the opener is unspecified.
- **Citations** — required, optional, or not used. If required, specify the format verbatim.
- **Schema, not prose** — for strict formats (JSON, fixed field sets), use the provider's structured-outputs or tool-use schema facility instead of prose instructions like "respond with JSON". Schemas enforce; prose requests drift. Same principle for citations — Anthropic's Citations API beats "please cite your sources" for accuracy-critical work.

### Source Hierarchy
When sources conflict, which wins? Without an explicit rule, the agent silently picks one and you can't predict which.

> "Prefer the knowledge base over your training knowledge. Prefer the current user message over the knowledge base. If the knowledge base and the user message contradict, say so and ask which to trust."

Three lines; removes an entire class of failure.

### Uncertainty — Give It the Exact Phrase
Name the phrases the agent should use when it doesn't know, or it will hallucinate or hedge with "it may be possible that...":

- "I don't have that information."
- "I'm not sure — can you confirm X?"
- "Based on <source>, but verify before acting on it."

Short list, instruction to pick from it when under its confidence threshold. This works more reliably than "don't hallucinate" because the agent has concrete phrasing to fall back on instead of inventing hedge language (and see Framing, above).

### Escalation / Handoff
When does the agent give up, and how?

- **Explicit triggers** — user says "talk to a human", "this isn't working", etc.
- **Implicit triggers** — 3 failed clarifications, detected frustration markers, topic outside scope.
- **Handoff sentence** — the exact words to use.
- **State to pass along** — what context to summarize for the next handler.

Agents without escalation either loop forever or bail on the first friction.

## Tool Descriptions Are Part of the Prompt

Tool descriptions are system-prompt text the model reads every turn. Every rule above applies to them:

- Positive framing: "Use `search_docs` for questions about product behavior" beats "Don't invent product facts."
- Reasoning: "Returns up to 10 results; re-query with a narrower phrase if none match" lets the agent recover from a bad search instead of giving up.
- Disambiguate overlapping tools by naming the boundary: "`search_docs` for documentation; `search_tickets` for customer history."

Schemas, cache breakpoints, and SDK wiring belong in `claude-api`. This skill covers the prose inside the description fields — which is where most tool-use failures actually originate.

## Examples Beat Rules for Style

One concrete example is worth three paragraphs of style guidance. The agent imitates a shown example more reliably than it follows a description of one.

- Show 2-4 examples covering the *span* of cases you care about, not just the happy path. Include one refusal and one clarification example.
- Examples should model **tone and shape**, not facts. Don't teach knowledge through examples; teach structure.
- **When examples drift from the rules, the examples win.** Audit them whenever you change the rules — stale examples silently override written guidance.

## Internal Consistency

Every section of the prompt must agree with every other section. The agent reads the whole thing as one instruction and silently picks a winner when two sections disagree — and which one wins is not predictable. Common drift patterns:

- **Persona vs. output shape** — "Be warm and conversational" + "Respond in under 50 words" pulls in opposite directions. Tighten one.
- **Scope vs. tools** — if the scope says "answer questions about X" but the tool list exposes write-to-Y tools, the agent will invent use cases for them.
- **Clarification policy vs. output shape** — "Ask a question when ambiguous" + "Always respond with a single JSON object" leaves the agent no well-formed way to ask a question.
- **Examples vs. rules** — covered above; the canonical silent-override case.

Before shipping, read the prompt top-to-bottom once and flag any two sentences that would tell the agent to do different things in the same situation.

## Cold-Start Readability

The agent has no context outside the prompt. Every product term, tool name, workflow step, and persona role needs grounding the first time it appears. A prompt that says "when the user asks about the Workflow Dashboard, pull from the KB" assumes the agent knows what the Workflow Dashboard is, what the KB contains, and when to stop pulling. Either define terms in a glossary block at the top, or inline the definition on first use.

Quick test: read the prompt as if you had never seen the product. Any sentence whose meaning depends on unstated knowledge is a cold-start gap.

## Reasoning Models

On reasoning-capable models (Claude Opus 4.7 extended thinking, o3, DeepSeek R1, Gemini thinking): skip meta-instructions like "think step by step" (native to the trace), minimize few-shot on reasoning-heavy tasks (anchors the trace and suppresses exploration), avoid prescribed reasoning structure (degrades native strategy), and constrain only the final-answer format — leave the reasoning trace free. These caveats don't apply to classification, extraction, or grounded QA.

## Self-Verification Without a Test Suite

Coding agents can "run the tests". General agents have weaker equivalents, but naming them improves compliance materially:

- "Before sending, check that every factual claim has a cited source."
- "Before refusing, check whether a scoped partial answer is possible."
- "If your response is longer than 3 paragraphs, check whether the user asked for that much."

These are soft checks, but naming them outperforms omitting them.
