---
name: write-agent-prompt
description: "Guidelines for authoring the text that defines a general agent — system prompts, personas, guardrails, tool descriptions, example sets. LLM-agnostic. Load when writing or editing the prose that steers an agent's behavior (persona, scope, clarification policy, output shape, uncertainty, escalation). For CLAUDE.md / AGENTS.md / coding-agent docs use write-agent-docs instead. For SDK wiring, prompt caching, and tool-use mechanics use claude-api."
---

# Writing Agent Prompts

Principles for the *text* that defines a production agent. LLM-agnostic. Sibling skills:
- `write-agent-docs` — CLAUDE.md / AGENTS.md for coding agents.
- `claude-api` — SDK wiring, caching, tool-use mechanics (the *how-to-call*, not the *what-to-say*).

## Skill Priority

When a request straddles sibling-skill boundaries, apply skills in this order:

1. Writing agent-facing documentation (CLAUDE.md, AGENTS.md, `.claude/rules/`) — use `write-agent-docs`; it supersedes this skill.
2. Configuring the SDK runtime (instantiation, tool schemas, prompt caching, tool-use loops) — use `claude-api`; it supersedes this skill.
3. Writing the prose the model reads as instruction (persona, scope, rules, tool descriptions, few-shot examples) — this skill.

A single task often needs all three in sequence: structure the docs with `write-agent-docs`, write the prose inside with this skill, configure SDK wiring with `claude-api`.

## Glossary

Terms used repeatedly below. Skim once; referenced implicitly thereafter.

- **Iron Law** — an absolute, no-exceptions rule paired with the specific workarounds it blocks (the "loophole list").
- **Baseline run** — running the target scenario with *no* rule in place, as a control. You watch the agent fail, capture the failure mode, and write the rule against that observed behavior rather than an imagined one.
- **Rationalization table** — a `| Excuse | Reality |` two-column table paired with a rule. Rows are the justifications the agent has produced, verbatim, for violating the rule.
- **Red Flags** — specific phrases the agent says right before violating a rule. Naming them converts inner monologue into a stop signal.
- **Long-context deployment** — a prompt or conversation large enough to degrade early-token salience: roughly >100k tokens in the prompt, or >50 conversation turns, or more than half of the model's context window filled.
- **Scripted redirect** — a verbatim sentence for declining off-topic requests, instead of "refuse politely".

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

### Harden Rules Against Rationalization
Positive framing and reasoning are the floor. Rules that survive pressure carry three further moves — each cheap to add and each targeted at a distinct erosion mode.

**Iron Law with enumerated loopholes.** An absolute rule followed by the specific workarounds it blocks, by name. Agents invent exceptions fluently; the enumeration pre-empts each one.

> NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.
> No exceptions: don't keep the draft as "reference", don't "adapt" it while writing tests, don't look at it. Delete means delete.

Harvest the loophole list from baseline runs — each line is an excuse an agent actually produced, not one you imagined.

**Rationalization tables.** A two-column `| Excuse | Reality |` table paired with the rule, one row per observed justification.

| Excuse | Reality |
|---|---|
| "Keep as reference" | You'll adapt it. That's testing after. Delete means delete. |
| "Tests after achieve the same purpose" | They test what you wrote, not what you should have written. |
| "TDD is dogmatic, I'm being pragmatic" | Pragmatism skipped the step that catches the worst bugs. |

The table is a vaccine. Every new baseline run that surfaces a fresh excuse is another row.

**Red Flags — the agent's own self-talk as trigger.** List the phrases the agent says *right before* violating the rule. The list converts inner monologue into a stop signal.

> Red flags — if you're thinking any of these, stop:
> - "I'll just add this one quick fix"
> - "I already manually tested it"
> - "This is different because..."
> - "Keep as reference"
> - "Should be fine"

This is the single highest-leverage move for rule compliance — it turns the agent's attention toward the rule at the exact moment it's being rationalized away.

### Rules Are Harvested, Not Invented
Rationalization tables and Red Flags only work if their rows are real. The loop:

1. **Baseline** — run the target scenario with the rule absent (or deliberately weak) so the failure has room to appear. Watch the agent fail, and capture the exact failure mode — that's the thing the rule is being written against.
2. **Record** — capture the agent's rationalizations verbatim. Those phrases become your table rows and Red Flags.
3. **Write** — draft the Iron Law, the loophole list, the table, the Red Flags.
4. **Pressure-test** — re-run under combined pressure (time, sunk cost, authority claims, exhaustion). The agent should comply.
5. **Refactor** — new rationalization surfaces? Add the row. Loop.

Prompts written without this loop read as checklists of tactics. Prompts written with it read as dense with closed loopholes — the only form that holds under pressure.

### When NOT to Harden a Rule
Hardening costs attention budget and signals importance. Apply it selectively:

- If you haven't baseline-tested the rule under pressure, don't harden it yet — you'll be guessing at excuses and red flags instead of harvesting real ones.
- If the rule isn't load-bearing (no observed cost when it slips), don't harden it — or cut the rule.
- If every rule in the prompt is hardened, hardening stops catching the eye and becomes bloat. Reserve it for the 2-3 rules where slippage actually hurts.

Red flags — if you're thinking any of these while choosing whether to harden, stop:
- "We'll harden it preemptively, just in case."
- "This rule *should* be critical, even though we haven't seen it break."
- "More hardening is always better."

### Weak Language Dilutes Everything
- **Weak modals** — "should", "try to", "ideally", "prefer to". Rewrite as directives. If it's genuinely optional, say so and name the condition ("MAY ... when ...").
- **Weasel phrases** — "use appropriate tone", "as needed", "generally", "if relevant". Escape hatches. Replace with concrete conditions.
- **Unmeasurable quality** — "be helpful", "be friendly", "write naturally". The agent can't evaluate these. Make them checkable ("address the user by first name when known") or cut them.
- **Aggressive emphasis** — "YOU MUST", "CRITICAL", "NEVER EVER". Calm, direct instructions perform better on modern models. Reserve caps/bold for the 2-3 rules that actually matter; overuse dilutes all of them.

### Instruction Count vs. Compliance

> **Iron Law: Every rule you add weakens compliance with every other rule. Before adding rule N+1, delete one — there is no free rule.**

Compliance degrades roughly monotonically with prompt length. Formatting constraints hold up under load; semantic and compositional constraints break first — cut the fuzzy ones first.

**Loopholes this rule blocks:**
- Don't keep a rule because "it's documented elsewhere too" — that's duplication, not a second instance of the rule.
- Don't add a rule because "it only applies in edge cases" — edge cases are where agents rationalize worst, and the rule competes for attention in all the common cases too.
- Don't add a rule "until we get more data" — you're in a baseline run right now; gather the data.
- Don't assume "the current model handles this automatically" — every model has failure modes and none of them excuses a rule that should exist.

| Excuse | Reality |
|---|---|
| "This rule is too important to cut" | Importance is inversely correlated with length. State it tersely or cut the noise around it. |
| "But we need clarity on this edge case" | Clarity on an edge case muddles the center. Re-order or rely on the base model. |
| "Other tools require this context" | That's a dependency you can dissolve — rename a field, add an XML tag, move the constraint into schema. |
| "The base model gets this wrong" | Focus your rule there; don't scatter fixes across twenty adjacent rules. |

Red flags — if you're thinking any of these while drafting, stop and cut a rule instead:
- "We need to handle this case too."
- "Just one more clarification."
- "This rule only applies when X." (Conditional rules are the weakest rules.)
- "This is an important safety boundary." (Then put it in one place, hardened; don't sprinkle.)

**Placement.** In prompts past ~20 lines, put the rules you care most about at the **top or bottom**. The middle 40-60% is the lowest-attention zone in most current LLMs. In long-context deployments (see glossary — roughly >100k tokens, >50 turns, or more than half the window filled), earliest tokens can also lose salience, so head-placement alone isn't a safety net; mirror critical rules at the tail in those cases.

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

**This skill's own persona (modeling the guidance):**
- Register — technical, direct, evidence-based; no hedging.
- Address — second person ("you", "your prompt").
- Sign-off — none; instructional register, each section self-contained.
- Self-reference — "the skill", "this guidance"; avoid "we".
- Domain posture — peer expert offering a methodology, not a careful advisor weighing options.

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

Ask one question per turn; when the input is ambiguous in multiple ways, resolve the highest-impact ambiguity first and circle back for the rest on a later turn. Stacked questions feel like interrogation and users answer only the last one.

Before asking anything, re-read the user's current message — if the answer is already there, proceed silently. Asking about facts the user already stated reads as inattention and spends a turn on nothing. (Example: the user says "delete all files older than 7 days"; don't ask "how many days?" — they said 7.)

Agents with no clarification policy default to asking three questions on every ambiguous input — a measurable UX failure.

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

Tool descriptions are system-prompt text the model reads every turn. Apply the same principles — positive framing, reasoning, rule economy — already covered in *The Content Core*; don't re-teach them here, apply them to each tool field.

**Disambiguate overlapping tools by naming the boundary.** When two tools have similar purposes, state explicitly which to use when, including a tie-breaker. Example: "`search_docs` for product documentation and behavior; `search_tickets` for customer history and past incidents. If the query could match either, start with `search_docs`." Without a boundary statement, agents either try both tools (wasting turns and tokens) or pick one without a stable heuristic — behavior that looks random to users.

A combined example demonstrating the three moves in one description: "Use `search_docs` for product questions (positive framing). Returns up to 10 results; narrow the phrase if none match (recovery reasoning). Prefer this over `search_tickets` unless the question is about a specific customer incident (boundary)."

Schemas, cache breakpoints, and SDK wiring belong in `claude-api`. This skill covers the prose inside description fields — which is where most tool-use failures actually originate.

## Examples Beat Rules for Style

One concrete example is worth three paragraphs of style guidance. The agent imitates a shown example more reliably than it follows a description of one.

- Show 2-4 examples covering the *span* of cases you care about, not just the happy path. Include one refusal and one clarification example.
- Examples should model **tone and shape**, not facts. Don't teach knowledge through examples; teach structure.
- **When examples drift from the rules, the examples win.** A contradiction between an example and a rule is a signal the *rule* is wrong — the example shows what the prompt actually produces — so prefer fixing the rule to fixing the example. Audit examples whenever you change a rule; if you can't keep them synchronized, delete the rule and rely on the example.

**Example refusal** (models a scripted redirect: short, no apology, names the next step):

> User: Can you recommend a stock to buy?
> Agent: I can't recommend specific investments. For that, talk to a licensed advisor. If you have questions about account features or fees, I can help with those.

**Example clarification** (models one narrow question, not a menu):

> User: Filter orders by amount.
> Agent: Do you mean total invoice amount, or per-line-item amount? I'll go with total invoice unless you say otherwise.

These model the *shape* — opening line, length, exactly one question, assume-and-proceed fallback — not any particular domain.

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

**Self-checks for prompt writers, before shipping:**

- Every rule has explicit reasoning — at minimum a one-sentence "because X" clause, or inherits it from a nearby paragraph.
- All load-bearing rules (forbidding high-impact actions, or referenced by other rules) sit in the top or bottom 25% of the prompt, not the middle 40-60%.
- No two sections tell the agent to do different things in the same situation (read top-to-bottom once; flag conflicts).
- None of the principles this skill teaches — positive framing, weak-language hygiene, persona-as-operational, scope-as-scripted — is violated by your own prompt prose.
- Every Iron Law is hardened (loopholes enumerated, rationalization table if it recurs, Red Flags) — and every rule that *isn't* an Iron Law is stripped of hardening so the signal stays legible.

These are soft checks, but naming them outperforms omitting them.
