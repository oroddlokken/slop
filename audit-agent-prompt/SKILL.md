---
name: audit-agent-prompt
description: "Audit general-agent prompts (system prompt, persona, scope, guardrails, tool descriptions, few-shot examples) for framing issues, weak language, missing reasoning, and the operational gaps that cause agent UX failures. LLM-agnostic. Use when the user wants to review or improve a production agent's prompt. For CLAUDE.md / AGENTS.md / coding-agent docs use audit-agent-docs instead. For SDK wiring, prompt caching, and tool-use mechanics use claude-api."
---

# Audit Agent Prompt

Spin up parallel sub-agents to audit a general agent's prompt from multiple critical angles, then distill findings into concrete proposed edits.

## Key Principle

This is an audit of the *text that steers an LLM agent's behavior* — system prompts, personas, scope definitions, guardrails, tool descriptions, and few-shot examples. These prompts have failure modes distinct from CLAUDE.md / AGENTS.md docs:

- Negative prohibitions ("NEVER mention competitors") trigger the pink-elephant effect and make the failure mode *more* available
- Weak language ("should", "try to", "use appropriate...") gives the agent an escape hatch from every rule
- Missing operational persona (register, address, sign-off) produces inconsistent voice
- No clarification policy → the agent asks three questions on every ambiguous input
- No scripted refuse sentence → the agent rambles apologetically on off-topic requests
- No uncertainty phrasebook → the agent hallucinates or hedges with "it may be possible that..."
- Examples that drift from the rules silently override the rules

This skill is LLM-agnostic. For coding-agent docs (CLAUDE.md, AGENTS.md) use `audit-agent-docs`. For SDK wiring / caching / tool-use mechanics use `claude-api`.

## Lenses

Each lens is a sub-agent with a specific critical angle. The user can run all or pick specific ones.

### Core Lenses (default)

1. **Framing (Pink Elephant)** — Find negative prohibitions that should be positive directives. LLMs attend to what you mention; "NEVER discuss competitors" activates "competitors" in the model's attention. For every NEVER / DO NOT / "don't" / "never" rule: quote it, explain the pink-elephant risk, and propose a positive rewrite. The only exception: keep NEVER/DO NOT for truly catastrophic, irreversible actions (PII disclosure, destructive tool calls) where the shock value is warranted. Every remaining prohibition must state what the agent should do *instead* — a rule that only says "no" leaves the agent guessing.

2. **Reasoning (Why)** — Find rules without an explanation. Rules with a "why" handle novel edge cases; rules without one break at the first surprise. For each bare rule, propose the reasoning.
   - Weak: "Use complete sentences."
   - Strong: "TTS engines can't pronounce ellipses or markdown, so use complete sentences in voice responses."

3. **Weak Language** — Flag and propose rewrites for:
   - **Weak modals**: "should", "consider", "try to", "ideally", "prefer to". Rewrite as directives. If genuinely optional, say so: "MAY ... when ...".
   - **Weasel phrases**: "use appropriate tone", "as needed", "if relevant", "generally", "usually", "normally", "typically". Replace with concrete conditions.
   - **Unmeasurable quality**: "be helpful", "be friendly", "write naturally", "use best judgment". Replace with checkable criteria or delete.
   - **Aggressive emphasis**: "YOU MUST", "CRITICAL", "NEVER EVER", "ABSOLUTELY". Reserve emphasis for the 2-3 rules that actually matter; overuse dilutes all of them.

4. **Platitudes & Defaults** — Find rules that restate base-model behavior: "be polite", "answer the user's question", "don't be offensive", "use proper grammar", "be accurate". Test: if inserting "not" somewhere would leave the rule still generally true, it's a platitude. Delete — these dilute the rules that carry information. Every rule you add weakens compliance with every other rule; there is no free rule.

5. **Redundancy & Brevity** — Find duplicated rules across sections, count total rules, and flag critical rules buried in the 40-60% zone of prompts >= 20 lines (LLMs pay less attention to the middle of long documents). Recommend consolidation and relocation of critical rules to the top or bottom.

6. **Contradictions** — Flag intra-prompt conflicts between sections (e.g., persona says "be brief", output shape says "explain thoroughly"). Pay special attention to **examples contradicting rules** — when examples drift from written rules, the examples win silently. For each: quote both passages, explain the conflict, recommend which wins.

7. **Persona (Operational, not Emotional)** — Flag emotional adjectives without operational definition ("be warm", "be helpful", "be professional"). Check that these operational attributes are specified concretely:
   - **Register** — match user's formality, or fixed?
   - **Address** — first name, title, none, inherit from session?
   - **Sign-off** — every message, never, only on resolution?
   - **Self-reference** — "I", "we", or none?
   - **Domain posture** — peer expert vs. careful advisor presenting options?

   For each missing attribute, propose a concrete setting. 4-6 concrete operational settings beat any number of adjectives.

8. **Scope & Redirect** — Is the covered scope stated explicitly and positively? Is there an *exact* redirect sentence for off-topic requests, or just "refuse politely"? Scripted redirects produce deterministic behavior. Propose a covered-scope sentence and a verbatim redirect sentence.

9. **Clarification Policy** — Is there an explicit rule for when to proceed / ask / assume-and-proceed? Without one, agents ask three questions on every ambiguous input — a measurable UX failure. Check for:
   - Proceed silently when one reasonable interpretation + cheap-to-recover
   - Ask exactly one question when high cost + narrow ambiguity (binary or short enumerable list)
   - State assumption and proceed when ambiguity is open-ended

   Also flag multi-question-at-once patterns and questions whose answer is already in the user's message.

10. **Output Shape** — Flag missing specifications. Leave shape vague and responses drift long and generic:
    - **Length target** — exact ("1-3 sentences", "under 100 words"), not "be concise"
    - **Structure** — bullets / prose / table / JSON — pick one per response type
    - **Opening** — forbid throat-clearing ("Great question!", "Certainly!", "I'd be happy to help"); state what the first line should actually say
    - **Citations** — required / optional / banned; if required, specify format verbatim

11. **Uncertainty Phrases** — Is there a named list of exact phrases for "I don't know" states? Generic "don't hallucinate" underperforms a short phrasebook by a wide margin. Propose a phrasebook if missing, e.g.:
    - "I don't have that information."
    - "I'm not sure — can you confirm X?"
    - "Based on <source>, but verify before acting on it."

12. **Guardrails** — Explicit safety boundaries for destructive or irreversible actions (data mutation, external messages, PII handling, tool calls that modify state). Check:
    - Stated positively with scope, not just "be careful with..."?
    - Reasoning included so the agent generalizes to novel cases?
    - Backed by enforcement (tool allow-lists, deny rules) or prose-only?

    Flag prose-only restrictions on dangerous actions — prose guides cooperative behavior but is not a security boundary and can backfire via pink elephant. For each: propose positive reframing with reasoning, and note whether an enforcement layer exists.

### Full Lenses (add to core)

13. **Source Hierarchy** — When the agent has multiple sources (knowledge base, training, retrieved docs, current user message), is there an explicit priority rule? Without it, the agent silently picks one and you can't predict which. Example of a good rule:

    > "Prefer the knowledge base over training knowledge. Prefer the current user message over the knowledge base. If the knowledge base and the user message contradict, say so and ask which to trust."

    Propose a three-line priority rule if missing.

14. **Escalation / Handoff** — For agents with human handoff: are triggers named (explicit — user says "talk to a human"; implicit — N failed clarifications, frustration markers, out-of-scope topic)? Is the exact handoff sentence given? Is the state-to-pass to the next handler specified? Flag missing pieces. Agents without escalation either loop forever or bail on the first friction.

15. **Tool Descriptions** — Tool description fields are system-prompt text the model reads every turn. Apply lenses 1-4 to every tool description. Additionally check:
    - Is the boundary between overlapping tools named? ("`search_docs` for product behavior; `search_tickets` for customer history.")
    - Is recovery guidance present? ("Returns up to 10 results; re-query with a narrower phrase if none match.")
    - Are arguments documented with examples where the format matters?

16. **Examples** — For few-shot examples:
    - Do they span the cases (happy path + refusal + clarification + edge case), or only the happy path?
    - Do any examples contradict the written rules? Flag as high-severity — examples win over rules silently.
    - Are examples teaching *shape* (tone, structure, length) or teaching *knowledge* (facts)? Teaching knowledge via examples is a code smell — facts belong in the knowledge base, examples should model structure.

17. **Self-Verification** — Are soft-check instructions named? Examples:
    - "Before sending, check that every factual claim has a cited source."
    - "Before refusing, check whether a scoped partial answer is possible."
    - "If your response is longer than 3 paragraphs, check whether the user asked for that much."

    These are cheap to add and measurably improve compliance.

18. **Cold Start** — Pretend to be a fresh LLM with zero context outside the prompt. What assumptions does the prompt make? (Product knowledge, jargon, workflow steps, user profile fields, tool semantics.) Flag anything the prompt references but doesn't define.

19. **Reasoning-Model Fit** — If the target prompt deploys on a reasoning-capable model (Claude Opus 4.7 extended thinking, o3, DeepSeek R1, Gemini thinking), flag patterns that degrade on these models:
    - Redundant meta-instructions ("think step by step", "reason carefully") — native to the thinking trace; compete with it.
    - Heavy few-shot blocks on reasoning-heavy tasks — anchor the trace and suppress exploration.
    - Prescribed reasoning structure ("first analyze X, then Y") — often beats the model's native strategy in the wrong direction.
    - Output-shape constraints bleeding into the reasoning trace — constrain only the final answer, leave the trace free.

## Workflow

### Step 1: Determine Target

Ask the user for target path and scope before launching agents — running on assumed defaults misfires because prompt layouts vary too widely to guess.

- **Path**: Point at the directory containing the agent prompt (or a single file if the whole prompt is one file). The skill will auto-discover system prompt, tool descriptions, examples, and guardrail files.
- **Scope**: Ask the user to pick one:
  - `standard` (recommended) — runs the 12 core lenses: framing, reasoning, weak language, platitudes, redundancy, contradictions, persona, scope & redirect, clarification policy, output shape, uncertainty, guardrails
  - `full` — everything above plus source hierarchy, escalation, tool descriptions, examples audit, self-verification, cold start, reasoning-model fit
  - Or the user can name specific areas (e.g., "just check framing and weak language")

Present as a simple choice — do NOT list lens numbers or internal names.

Wait for the user's response before moving to Step 2.

### Step 2: Discover Prompt Files

Use the user's target as the scope root. Only discover files that exist on disk inside that root — never pull in content from conversation context, global configs, or user home directories.

**2a. Auto-discover by common names and locations:**

| Component | Patterns (relative to target root) |
|---|---|
| System prompt | `system.md`, `system_prompt.md`, `prompt.md`, `persona.md`, `instructions.md`, `PROMPT.md`, `SYSTEM.md`, `system.txt` |
| Tool descriptions | `tools/**/*.{md,yaml,yml,json}`, `tool_descriptions/**`, `*.tool.{md,json,yaml,yml}` |
| Examples / few-shot | `examples/**`, `few_shot/**`, `shots/**`, `examples.{md,jsonl,json}`, `fewshot.{md,jsonl,json}` |
| Guardrails / policies | `guardrails.md`, `safety.md`, `policies.md`, `safeguards.md` |
| Config-embedded prompts | `*.{yaml,yml,json}` — scan for keys `system`, `system_prompt`, `instructions`, `prompt`, `persona` at any depth |

**2b. Fallback — ask the user (option c)**: If auto-discovery finds no plausible prompt files, list every `.md`, `.txt`, `.yaml`, `.yml`, `.json` file in the target path (up to ~20) and ask the user to label which file is which component (system prompt / tool descriptions / examples / guardrails / other / skip). Skip files labeled "other" or "skip".

**2c. Extract embedded prompts**: If a discovered config file has a string value under `system:` / `system_prompt:` / `instructions:` / `prompt:` / `persona:`, extract the string and treat it as a system prompt, recording its origin (`config.yaml → system_prompt`).

**2d. Report the snapshot** — before launching lenses, list what was discovered, with filename + classification + line count. Example:

> Discovered:
> - `prompt.md` — system prompt (134 lines)
> - `tools/search_docs.md` — tool description (22 lines)
> - `tools/create_ticket.md` — tool description (31 lines)
> - `examples/refusal.md` — few-shot example (18 lines)
> - *(No guardrails file found — will audit inline guardrails in system prompt only.)*

Read all discovered files and pass their contents (paths relative to target root, with line numbers) to each lens agent.

### Step 3: Launch Agents

Use the agent template (`audit-agent.md`). Shared content (key principle, prompt snapshot, output format) sits before the `---` divider to form a cacheable prompt prefix.

**Launch strategy** — ask the user:

- **Sequential** (default) — launch agents one at a time, each after the previous completes. First agent primes the cache; every subsequent agent reads the shared prefix at ~90% cheaper input. Slowest, cheapest.
- **1+Parallel** — launch one agent first to prime the cache, then launch the rest in parallel batches of at most 5. Anthropic rate-limits large simultaneous bursts, so batching past 5 triggers 429s mid-run and wastes work. Nearly as cheap as Sequential, much faster.

If the user doesn't specify, use **Sequential**.

**Placeholder resolution:**
1. Read `audit-agent.md` from this skill's directory
2. Replace `{prompt_snapshot}` with all discovered files (paths + line-numbered contents)
3. Replace `{path}` with the target root
4. Replace `{discovered_components}` with the Step 2d report
5. For each selected lens:
   - Replace `{lens}` with the lens name (e.g., `Framing (Pink Elephant)`)
   - Replace `{lens_instructions}` with the lens-specific instructions from the Lenses section above
   - Pass the result as the agent prompt

Use `subagent_type: "Explore"` for all agents so they can read related files if needed.

### Step 4: Distill

After all agents complete:

1. **Deduplicate**: Multiple lenses often flag the same issue (e.g., "NEVER mention competitors" fails both Framing and Guardrails). Merge, noting which lenses flagged it.

2. **Classify** each finding:
   - **Remove** — platitudes, redundancies, rules restating base-model defaults
   - **Rewrite** — weak language, negative framing, bare rules without reasoning, weasel phrases
   - **Add** — missing persona attributes, uncertainty phrasebook, clarification policy, redirect sentence, source hierarchy, escalation
   - **Move** — critical rules buried in the middle of long prompts

3. **Propose concrete edits**: exact file, current text (quoted with line numbers), proposed new text. Group by file.

4. Output as:

```
## Audit Results

### File: {filename}

#### {Remove|Rewrite|Add|Move}: {title}
**Flagged by**: {lens names}
**Current** (lines N-M):
> {quoted text}
**Proposed**:
> {new text or "delete" or "move to top"}
**Why**: {one line}

---

### Summary
- {N} negative prohibitions to reframe
- {N} bare rules that need reasoning
- {N} weak-language rewrites
- {N} platitudes to remove
- {N} redundancies to consolidate
- {N} contradictions to resolve
- {N} persona gaps
- {N} missing operational attributes (scope & redirect, clarification, output shape, uncertainty, guardrails)
```

5. After outputting, ask the user: "Want me to apply these changes?"

## Rules

- **Ask the user for launch strategy** (Sequential or 1+Parallel). Default to Sequential for cost savings.
- **Each agent audits independently** — crossing findings between agents biases the later runs; cross-lens agreement at the distill step is the signal that a finding is robust.
- **Distill runs after all agents complete** — multiple lenses often flag the same issue from different angles, and deduplication needs all findings in hand.
- **Propose edits and wait for user approval before applying them** — the user is the arbiter of which changes are worth the code churn.
- **Scope strictly to the prompt files discovered in the target.** Pulling rules from conversation context, CLAUDE.md, or global configs produces findings the user can't act on — they don't control those inputs.
- **LLM-agnostic**: audit the prompt's text, not its deployment platform. Claude-specific infrastructure (`.claude/rules/`, skills, hooks) only belongs in findings when the target prompt is demonstrably a Claude Code prompt; otherwise it's advice the user can't use.
