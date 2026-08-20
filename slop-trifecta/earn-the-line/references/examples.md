# earn-the-line: worked examples

Bad/good pairs for the rules in `../SKILL.md`. Each heading names the rule it
pairs with. The rules are injected at session start; these pairs are not.

## Names that appear verbatim below

<example>
Bad, above a function that passes those three strings on its next three lines —
`// Env vars: TIMEOUT_CONNECT_MS, TIMEOUT_READ_MS, TIMEOUT_WRITE_MS (milliseconds).`

Good: nothing. The names are below it and the `_MS` suffix carries the unit.
</example>

## One comment for a set, not one per declaration

<example>
Bad:
`# port1 - untrust / external` over `resource "azurerm_subnet" "fortigate_external_subnet"`, then `# port2 - trust / internal` over `..._internal_subnet`, once per resource.

Good: one comment for the set, carrying what the names cannot —
`# NIC order is fixed by the image: port1 external, port2 internal, port3 HA sync.`
</example>

## Open on the fact

<example>
Bad: `// Size of the buffer in bytes; must be a power of two or the ring wraps wrong.`
Good: `// Must be a power of two: the ring masks instead of dividing.`
</example>

## Four lines, two sentences

<example>
Good, four lines and two sentences above one `iptables` rule —
`# Must precede the tailnet ACCEPT: the kernel takes the first`
`# match, and this DROP keeps the forwarded range out. Reordering`
`# these two lines opens the range with no other symptom, so the`
`# test asserts on rule order.`
</example>

## File headers

<example>
Bad: ten box-drawn lines over the first resource, explaining the whole NVA and
route-server topology, in a file that declares four subnets.

Good: no header; the one non-obvious constraint sits on the line it constrains —
`# RouteServerSubnet must be named exactly that and cannot share the NVA range.`
</example>

## The fix, not the hunt

<example>
Bad, above the grant that fixed it —
`# this grant is the half that was missing, and its absence reads as a routing`
`# fault rather than an ACL -- ping answers while every TCP port times out.`

Good: `# tag:ingress resolves to proxy2 alone; tag:vps would name irc2 too.`
</example>

## Scope to what the file can be changed to say

<example>
Bad: `# Each Fortigate must peer with both Route Server instances. That is configured on the Fortigate side, not here.`

Good: `# ASN must be 16-bit and not 65515; Route Server rejects both.`
</example>

## Prose in a generator's field

<example>
Bad: the egress rationale in a manifest's `summary`, its `notes`, its
`env_notes`, and again on the tailnet grant that permits the egress.

Good: the rationale on the grant; nothing in the manifest.
</example>

## A shortened copy is still a copy

<example>
Bad, and still a copy at one line —
`# Console transcripts piped by hand; the JSONL beside them is parseable and committed.`

Good: `results/logs/*.log` with nothing above it.
</example>

## Point at the doc

<example>
Bad, three lines above one ignore rule standing among four bare ones —
`# The JSONL receipts beside these are committed on purpose - see evals/README.md.`
`# Only hand-piped console transcripts are ignored: they duplicate the receipt in`
`# a form nothing can parse.`

Good: the rule alone, or one pointer if the exception will not survive without
one — `# why: evals/README.md, "The receipt"`.
</example>

## No ticket ids

<example>
Bad: `# entries bucket by local calendar day in the display zone (vekt-52r9)`
Good: `# bucket by local day: a 23:30 Oslo entry lands on tomorrow in UTC`
</example>

## Delete, do not annotate

<example>
Bad: `## Rule 9: Cap lists at 5 items — restored 2026-08-10 in the style's opening block`, and `11. (restored 2026-08-10 in "Before sending")` under it.
Good: the heading and the item both deleted outright.
</example>

## Empty states and errors

<example>
Bad: "Uncommitted changes. Commit or stash — nothing here touches your working tree, so you are safe either way."

Good: "Uncommitted changes. Commit or stash."
</example>

## When a control could be mistaken for deletion

<example>
Bad: "Exclude a stream that is not history worth counting — a test broadcast, or a reconnect recorded as its own stream. Nothing is deleted: the stream stays on this page and in the lists, and drops out of every stat."

Good: "Excluding drops this stream from every duration, average, count and category total. It stays on this page and in the lists."
</example>

## An unknown gets one line

<example>
Bad, a fallback chain where the gap is one line —
`# Unverified whether the API returns 429 or 503 under quota. If 429 the`
`# backoff below applies; if 503 the caller retries instead, and if neither`
`# the request fails closed.`

Good: `# Unverified: which status the API returns under quota.`
</example>

## When the convention requires the line

<example>
Bad, on an exported Go identifier, saying what the name says —
`// ParseTimeout parses the timeout.`

Good: `// ParseTimeout rejects a bare number: time.ParseDuration reads "5" as`
`// 5ns.` In the reply, one clause: "Go doc comment, required for the exported
name."
</example>

## When the user asks for the comment anyway

<example>
Asked for, above a retry loop —
`# Sets up the retry loop. Makes the service robust against transient upstream`
`# failures.`

Good: write it as asked, then one clause in the reply — "Written as asked; these
rules would have cut 'robust' and kept the retry count."
</example>
