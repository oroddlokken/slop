---
name: audit-agent-prompt
description: "Audit general-agent prompts (system prompt, persona, scope, guardrails, tool descriptions, few-shot examples) for framing issues, weak language, missing reasoning, and the operational gaps that cause agent UX failures. LLM-agnostic. Use when the user wants to review or improve a production agent's prompt. For CLAUDE.md / AGENTS.md / coding-agent docs use audit-agent-docs instead. For SDK wiring, prompt caching, and tool-use mechanics use claude-api."
---

# Audit Agent Prompt

Run one sub-agent that audits a general agent's prompt across all selected lenses in a single pass, then present the findings for user approval.

Agent prompts are small single-artifact targets. Multi-subagent dispatch (as in `audit-agent-docs`) adds per-agent startup and coordination overhead that dominates the audit cost when the target is one file. One agent applying many lenses in one pass is faster and cheaper.

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

## Scope

**In scope**: text that steers LLM agents — system prompts, personas, scope definitions, guardrails, tool descriptions, few-shot examples — for any agent that accepts user input and applies LLM reasoning (general-purpose agents, specialized domain agents, multi-turn dialogue systems, auditor/reviewer agents).

**Out of scope** (route the user elsewhere):
- CLAUDE.md / AGENTS.md / copilot-instructions.md / coding-agent framework docs → `audit-agent-docs`
- SDK wiring, prompt caching, tool-use runtime mechanics → `claude-api`

## Lenses

Each lens is a specific critical angle. The user picks a scope (standard, full, or a named subset) and all selected lenses are bundled into a single sub-agent prompt, applied in one pass.

### Core Lenses (default)

1. **Framing (Pink Elephant)** — Find negative prohibitions that should be positive directives. LLMs attend to what you mention; "NEVER discuss competitors" activates "competitors" in the model's attention. For every NEVER / DO NOT / "don't" / "never" rule: quote it, explain the pink-elephant risk, and propose a positive rewrite. **Exception (narrow)**: keep NEVER/DO NOT only for catastrophic, irreversible actions with no undo path (PII disclosure, destructive file or database operations). Every other prohibition must be rewritten as a positive directive stating what the agent should do *instead* — a rule that only says "no" leaves the agent guessing and increases the chance of the violation it forbids.

   When applying the exception clause, watch for these rationalizations:

   | Excuse | Reality |
   |---|---|
   | "It's a safety rule, so the pink-elephant effect doesn't apply" | Pink-elephant applies to all prose; safety topics are where drift is most costly. |
   | "The scope is small, so the prohibition is fine" | A single unrecoverable path still qualifies; blast radius matters, not frequency. |
   | "NEVER is more emphatic and the user will read it as serious" | Emphasis is the problem — it activates the forbidden concept in the model's attention. |

   Red Flags — if you catch yourself thinking any of these while auditing, re-read the exception clause:
   - "This prohibition feels important, so let it stay negative."
   - "There's no good positive rewrite, so leave it."
   - "Rewriting would weaken the rule."

2. **Reasoning (Why)** — Find rules without an explanation. Rules with a "why" handle novel edge cases; rules without one break at the first surprise. For each bare rule, write the reasoning as a causal chain: *because X, do Y*.
   - Weak: "Use complete sentences."
   - Strong: "Because TTS engines can't pronounce ellipses or markdown, use complete sentences in voice responses."

3. **Weak Language** — Flag and propose rewrites for:
   - **Weak modals**: "should", "consider", "try to", "ideally", "prefer to". Rewrite as directives ("Do X"). If genuinely optional, mark it: "MAY do X when Y".
   - **Weasel phrases**: "use appropriate tone", "as needed", "if relevant", "generally", "usually", "normally", "typically". Replace with concrete conditions — name the context or metric.
   - **Unmeasurable quality**: "be helpful", "be friendly", "write naturally", "use best judgment". Replace with checkable criteria (e.g., "cite sources", "under 100 words") or delete.
   - **Aggressive emphasis**: "YOU MUST", "CRITICAL", "NEVER EVER", "ABSOLUTELY". Limit to 2-3 true Iron Laws per prompt; overuse dilutes compliance with every rule.

4. **Platitudes & Defaults** — Find rules that restate base-model behavior: "be polite", "answer the user's question", "don't be offensive", "use proper grammar", "be accurate". Apply this test to every rule: *if inserting "not" somewhere would leave the rule still generally true of a base model, it's a platitude.* Delete platitudes — they carry zero information density. Every rule competes with every other rule for attention budget; there is no free rule.

5. **Redundancy & Brevity** — Find duplicated rules across sections, count total rules, and flag critical rules buried in the 40-60% zone of prompts >= 20 lines (LLMs pay less attention to the middle of long documents). A rule is **critical** if: (a) it forbids a high-risk action (destructive tool calls, PII disclosure, irreversible state change), OR (b) it is referenced or relied on by other rules in the prompt. Recommend consolidation of duplicates and relocation of critical rules to the top or bottom.

6. **Contradictions** — Flag intra-prompt conflicts between sections (e.g., persona says "be brief", output shape says "explain thoroughly"). Pay special attention to **examples contradicting rules** — when examples drift from written rules, the examples win silently. For each: quote both passages, explain the conflict, recommend which wins.

7. **Persona (Operational, not Emotional)** — Flag emotional adjectives without operational definition ("be warm", "be helpful", "be professional"). Adjectives like these add no information the base model doesn't already carry; the steering value comes from specifying concrete operational attributes. For each detected adjective, check whether these attributes are specified:
   - **Register** — match user's formality, or fixed?
   - **Address** — first name, title, none, inherit from session?
   - **Sign-off** — every message, never, only on resolution?
   - **Self-reference** — "I", "we", or none?
   - **Domain posture** — peer expert vs. careful advisor presenting options?

   For each missing attribute, propose a concrete setting. 4-6 concrete operational settings beat any number of adjectives.

8. **Scope & Redirect** — Is the covered scope stated explicitly and positively? Is there an *exact* redirect sentence for off-topic requests, or just "refuse politely"? Scripted redirects produce deterministic, repeatable behavior and prevent drift; vague instructions like "refuse politely" let the agent improvise with inconsistent tone and length. Propose a covered-scope sentence and a verbatim redirect sentence.

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

    (The sub-agent applies this to itself: when uncertain whether a pattern is a violation or a design choice, state it explicitly — *"Unclear whether X is intentional; if it is, add reasoning; if not, consider rewriting as Y"* — rather than hedging with "may" or "might".)

12. **Guardrails** — Explicit safety boundaries for destructive or irreversible actions (data mutation, external messages, PII handling, tool calls that modify state). Check:
    - Stated positively with scope, not just "be careful with..."?
    - Reasoning included so the agent generalizes to novel cases?
    - Backed by enforcement (tool allow-lists, deny rules) or prose-only?

    Flag prose-only restrictions on dangerous actions — prose guides cooperative behavior but is not a security boundary and can backfire via pink elephant. For each: propose positive reframing with reasoning, and note whether an enforcement layer exists.

13. **Rule Hardening** — For each Iron Law, critical prohibition, or rule the prompt actually relies on under pressure, check whether it is hardened against rationalization. Three defenses catch the exceptions that erode rules in production:
    - **Enumerated loopholes** — rules phrased as "NO X WITHOUT Y FIRST" must list the specific workarounds they are designed to block (from observed agent behavior, not abstract hypotheticals). Flag rules without enumeration — agents invent exceptions the author never anticipated. *How to harvest*: run the agent against the rule's target scenarios; each time it breaks the rule, note the workaround it used; add each as a "NOT when Z" clause.
    - **Rationalization tables** — is the rule paired with a `| Excuse | Reality |` table, each row a rationalization the agent actually produced (from baseline runs), with a rebuttal? Flag bare rules. Flag tables with only hypothetical excuses — they miss the rationalizations the agent actually produces. *How to harvest*: during baseline testing, capture the reasons the agent gives for the violation; write them verbatim as the "Excuse" column; write the rebuttal in the "Reality" column.
    - **Red Flags list** — does the prompt name the phrases the agent says right before violating the rule ("I'll just add this one quick fix", "I already manually tested it", "this is different because...")? Flag rules without this list. It's the single highest-leverage compliance move because it converts the agent's own self-talk into a stop signal. *How to harvest*: during baseline testing, capture the phrases that appeared immediately before the violation; add them to a Red Flags list with the instruction *"if you notice yourself saying any of these, stop and reread the rule"*.

    A rule with all three is dense with closed loopholes; a rule with only positive framing is the floor. This lens measures the ceiling. For each finding: quote the rule, note which of the three moves are missing, and propose what to add (using the harvest procedures above).

### Full Lenses (add to core)

14. **Source Hierarchy** — When the agent has multiple sources (knowledge base, training, retrieved docs, current user message), is there an explicit priority rule? Without it, the agent silently picks one and you can't predict which. Example of a good rule:

    > "Prefer the knowledge base over training knowledge. Prefer the current user message over the knowledge base. If the knowledge base and the user message contradict, say so and ask which to trust."

    Propose a three-line priority rule if missing.

15. **Escalation / Handoff** — For agents with human handoff: are triggers named with enumerated conditions?
    - **Explicit triggers**: user phrases like "talk to a human", "I want support", "escalate this".
    - **Implicit triggers**: "after 2 failed clarifications", frustration markers ("this is useless", "I'm giving up"), request outside documented scope.

    Is the exact handoff sentence given verbatim? Is the state-to-pass to the next handler specified (user ID, conversation summary, open questions)? Flag missing pieces. Agents without escalation either loop forever or bail on the first friction.

16. **Tool Descriptions** — Tool description fields are system-prompt text the model reads every turn. Apply lenses 1-4 to every tool description. Additionally check:
    - Is the boundary between overlapping tools named? ("`search_docs` for product behavior; `search_tickets` for customer history.")
    - Is recovery guidance present? ("Returns up to 10 results; re-query with a narrower phrase if none match.")
    - Are arguments documented with examples where the format matters?

17. **Examples** — For few-shot examples:
    - Do they span the cases (happy path + refusal + clarification + edge case), or only the happy path?
    - Do any examples contradict the written rules? Flag as high-severity — examples win over rules silently.
    - Are examples teaching *shape* (tone, structure, length) or teaching *knowledge* (facts)? Teaching knowledge via examples is a code smell — facts belong in the knowledge base, examples should model structure.

18. **Self-Verification** — Are soft-check instructions named? Examples:
    - "Before sending, check that every factual claim has a cited source."
    - "Before refusing, check whether a scoped partial answer is possible."
    - "If your response is longer than 3 paragraphs, check whether the user asked for that much."

    These are cheap to add and measurably improve compliance.

19. **Cold Start** — Pretend to be a fresh LLM with zero context outside the prompt. What assumptions does the prompt make? (Product knowledge, jargon, workflow steps, user profile fields, tool semantics.) Flag anything the prompt references but doesn't define. Agents without this context hallucinate definitions or fail silently; undefined references are a common source of behavior that looks random to users.

20. **Reasoning-Model Fit** — If the target prompt deploys on a reasoning-capable model (Claude Opus 4.7 extended thinking, o3, DeepSeek R1, Gemini thinking), flag patterns that degrade on these models:
    - Redundant meta-instructions ("think step by step", "reason carefully") — native to the thinking trace; compete with it.
    - Heavy few-shot blocks on reasoning-heavy tasks — anchor the trace and suppress exploration.
    - Prescribed reasoning structure ("first analyze X, then Y") — often beats the model's native strategy in the wrong direction.
    - Output-shape constraints bleeding into the reasoning trace — constrain only the final answer, leave the trace free.

## Workflow

### Step 1: Determine Target

Ask the user for target path and scope before launching agents — running on assumed defaults misfires because prompt layouts vary too widely to guess.

- **Path**: Point at the directory containing the agent prompt (or a single file if the whole prompt is one file). The skill will auto-discover system prompt, tool descriptions, examples, and guardrail files.
- **Scope**: Ask the user to pick one:
  - `standard` (recommended) — runs the 13 core lenses: framing, reasoning, weak language, platitudes, redundancy, contradictions, persona, scope & redirect, clarification policy, output shape, uncertainty, guardrails, rule hardening
  - `full` — everything above plus source hierarchy, escalation, tool descriptions, examples audit, self-verification, cold start, reasoning-model fit
  - Or the user can name specific areas (e.g., "just check framing and weak language")

Present as a simple choice — do NOT list lens numbers or internal names.

**Out-of-scope targets**: If the user points at a `CLAUDE.md`, `AGENTS.md`, or `copilot-instructions.md` file, respond verbatim: *"This looks like coding-agent documentation, not an agent prompt. Use the `audit-agent-docs` skill instead — it's tailored to framework docs. If you want to audit just the prompt text inside this file, point me at that section and I'll treat it as a standalone prompt."* Then stop and wait for the user to redirect.

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

**2b. Priority when multiple files match a component**: If two or more files match the system-prompt pattern list (e.g., both `system.md` and `prompt.md` exist), include all of them in the snapshot. Label the first match in the pattern list as the primary; label the rest as secondary. If the user's intent is unclear, ask: "I found both `X` and `Y`. Which is the main system prompt — or are they both in use?"

**2c. Fallback — ask the user**: If auto-discovery finds no plausible prompt files, list every `.md`, `.txt`, `.yaml`, `.yml`, `.json` file in the target path (up to ~20) and ask the user to label which file is which component (system prompt / tool descriptions / examples / guardrails / other / skip). Skip files labeled "other" or "skip".

**2c. Extract embedded prompts**: If a discovered config file has a string value under `system:` / `system_prompt:` / `instructions:` / `prompt:` / `persona:`, extract the string and treat it as a system prompt, recording its origin (`config.yaml → system_prompt`).

**2d. Report the snapshot** — before launching the agent, list what was discovered, with filename + classification + line count. Example:

> Discovered:
> - `prompt.md` — system prompt (134 lines)
> - `tools/search_docs.md` — tool description (22 lines)
> - `tools/create_ticket.md` — tool description (31 lines)
> - `examples/refusal.md` — few-shot example (18 lines)
> - *(No guardrails file found — will audit inline guardrails in system prompt only.)*

Read all discovered files. Format each as `### File: {relative_path} ({N} lines)` followed by the file contents with line numbers prefixed (e.g., `  1: `, `  2: `). Pass this formatted block as the `{prompt_snapshot}` placeholder.

### Step 3: Launch One Agent

Spawn a single sub-agent (`subagent_type: "Explore"`) that applies all selected lenses in one pass and returns consolidated, deduplicated findings. Do not spawn per-lens agents — the target is small and the coordination overhead is the slow part.

**Prompt assembly:**
1. Read `audit-agent.md` from this skill's directory.
2. Replace `{prompt_snapshot}` with all discovered files (paths + line-numbered contents).
3. Replace `{path}` with the target root.
4. Replace `{discovered_components}` with the Step 2d report.
5. Build the `{lenses}` block by concatenating the instructions for each selected lens from the Lenses section above. Format each lens as:

    ```
    ### Lens {N}: {lens name}
    {lens instructions verbatim}
    ```

6. Pass the assembled prompt to the agent. Wait for completion.

### Step 4: Present Findings

The agent returns findings already deduplicated (lenses that flagged the same issue are merged with all flagging lenses listed) and grouped by file, in the format specified inside `audit-agent.md`. Pass the output through to the user, then ask: "Want me to apply these changes?"

If the agent's output deviates from the expected structure, reformat it for presentation — do not re-audit or add new findings. The audit is the agent's.

## Constraints

- **One sub-agent, all selected lenses.** Agent-prompt audits target a single small artifact. Multi-subagent dispatch (as in `audit-agent-docs`) adds coordination overhead not justified here. Deploy one agent, apply all selected lenses in one pass.
- **The sub-agent deduplicates across lenses internally.** The same issue often trips multiple lenses (e.g., "NEVER mention competitors" violates both Framing and Guardrails). Merge duplicates into one finding; list all flagging lenses.
- **Propose edits; do not apply them.** Wait for user approval before making changes. The user decides which findings are worth the code churn.
- **Scope findings strictly to the discovered files.** Do not pull rules from conversation context, CLAUDE.md, or global configs — the user cannot act on findings tied to files they don't control.
- **LLM-agnostic output.** Audit prompt text, not deployment infrastructure. Mention Claude-specific tools (`.claude/rules/`, skills, hooks) only when the target prompt is demonstrably a Claude Code prompt; otherwise propose portable advice.
