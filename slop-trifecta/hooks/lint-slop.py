#!/usr/bin/env python3
"""PostToolUse check: flags the regex-safe subset of the shared prose rules --
cut-the-crap's "Before sending" inventories and its corrective-framing shapes,
plus earn-the-line's edit-annotation, empty-negation, session-address,
plan-reference and ticket-id rules; the labels in INVENTORY name the
categories. Copulative dodges, the tics that need a sentence to judge ("seam", "sharp edge") and hedging
adverbs are not matched; they need context a regex does not have.

Scans only the text the tool added, and only where prose lives -- every line of
a doc file, comment-shaped lines elsewhere, plus lines opening with a string
literal, where UI copy sits. A hit prints to stderr and exits 2, which shows the
message to the model after the write has landed.
"""

import json
import os
import re
import sys

# A tracker id shaped like macsetup-4xm3: the suffix must carry both a letter
# and a digit, which keeps utf-8, iso-8601 and cut-the-crap out. Only the
# parenthesised and referenced forms are matched; a bare hyphenated word is too
# often a real one.
_ID = (r"[a-z][a-z0-9]*-(?=[a-z0-9]{4,6}\b)"
       r"(?:[a-z0-9]*\d[a-z0-9]*[a-z][a-z0-9]*|[a-z0-9]*[a-z][a-z0-9]*\d[a-z0-9]*)")

# Corrective framing takes both halves: a negated copula opening a sentence,
# then the same subject restated affirmatively. "is not", "rather than" and
# "instead of" carry a fact on their own and stay out.
_SUBJ = r"(?:it|this|that|these|those)"
_NEG = (r"(?:['’]s not|\s+is not|\s+isn['’]?t|\s+are not"
        r"|\s+aren['’]?t|\s+was not|\s+wasn['’]?t|\s+were not"
        r"|\s+weren['’]?t)")
_POS = r"(?:['’]s|\s+is|\s+are|\s+was|\s+were)"

# A false positive teaches the model to ignore the hook, so everyday words that
# carry a real sense somewhere (just, key, actually, critical, harness) stay out
# of these lists.
INVENTORY = [
    ("puffery", r"\b(?:robust|comprehensive|seamless|elegant|sophisticated"
                r"|battle-tested|production-ready|enterprise-grade|first-class"
                r"|blazing fast|powerful|crucial|vital|pivotal|essential"
                r"|at its core|in essence|fundamentally)\b"),
    ("self-vouching", r"\b(?:genuinely|truly)\b"),
    ("coding-assistant tic", r"\b(?:foot-?gun|belt and suspenders|blast radius"
                             r"|surface area|load-bearing)\b"),
    ("softener", r"\b(?:simply|easily|clearly|obviously|straightforward"
                 r"|of course)\b"),
    ("throat-clearing", r"\bnote that\b|\bit'?s worth noting\b|\bkeep in mind\b"),
    ("inflated verb", r"\b(?:leverages?|leveraging|utiliz(?:e|es|ing)"
                      r"|delves?|delving|unpack(?:s|ing)?"
                      r"|orchestrat(?:e|es|ing)|unlock(?:s|ing)?"
                      r"|empower(?:s|ing)?|facilitat(?:e|es|ing))\b"),
    ("participle tail", r",\s*(?:ensuring|enabling|allowing for)\b"),
    ("corrective framing", r"(?:^\s*(?:[-*]\s+)?|[.;!?]\s+)" + _SUBJ + _NEG
                           + r"\b[^.;!?—]{1,60}(?:\s*[—,.;:]\s*|\s+-\s+)"
                           + _SUBJ + _POS + r"\b"),
    ("not-only framing", r"\bnot (?:just|only|merely)\b[^.;!?]{1,60}?\bbut\b"),
    # A negation carrying a whole bullet or line: the payload is the absence,
    # with no property named. Anchored to the line end, so "not used in dev"
    # and any negation a sentence continues past stay out.
    ("empty negation", r"(?:^|[-*—;:,.]\s*)\s*not "
                       r"(?:chosen|selected|picked|adopted|needed)\.?\s*$"),
    ("empty negation", r"\b(?:does|do|did) not apply(?:\s+(?:here|yet))?\.?\s*$"),
    # A line written to the person in the session: the reader months later was
    # not there. "as requested by the caller" is a fact about the code, so the
    # lookahead keeps it out.
    ("session address", r"\bas (?:you )?requested\b(?!\s+by)"
                        r"|\bper your request\b|\bat your request\b"
                        r"|\bas (?:we|you and I) discussed\b"
                        r"|\byou asked (?:for|me|us)\b"),
    # A plan's own numbering: the plan is a session artifact, so only the forms
    # pointing back at it are matched, never a bare "step 2".
    ("plan reference", r"\b(?:phase|step|task|stage|milestone)\s+\d+(?:\.\d+)?"
                       r"\s+(?:of|in|from)\s+(?:the\s+|our\s+|my\s+)?plan\b"
                       r"|\bper (?:the )?plan\b"),
    # The moved-clause needs its subject: a bare "moved to" is a fact about the
    # code as often as an annotation about the file's own history.
    ("edit annotation", r"\brestored 20\d\d|\bno longer needed\b"
                        r"|\bno longer cut\b|\b(?:this|it|that) moved (?:to|into)\b"),
    ("ticket id", r"[(\[]\s*" + _ID + r"\s*[)\]]"),
    ("ticket id", r"\b(?:see|refs?|fixes|closes|issue|ticket|bug)\s+#?" + _ID),
    ("ticket id", r"\b(?:PR|pull request|issue)\s+#\d+\b"),
]

RULES = [(label, re.compile(pattern, re.IGNORECASE)) for label, pattern in INVENTORY]

# Only a file that quotes the inventories is exempt, matched as a substring of
# the path. A whole tree is too wide: every other skill uses these words as
# prose, which is the case the hook exists to catch.
EXEMPT_PATHS = (
    "claude/output-styles/cut-the-crap.md",
    "claude/skills/earn-the-line/",
    "claude/skills/comment-cop/",
    "claude/skills/string-cop/",
    "claude/skills/audit-agent-docs/",
    "claude/skills/audit-agent-prompt/",
    "claude/skills/write-agent-docs/",
    "claude/skills/write-agent-prompt/",
    "claude/hooks/lint-slop",
    "claude/hooks/inject-earn-the-line",
)

PROSE_EXT = {".md", ".markdown", ".rst", ".txt"}

CODE_EXT = {
    ".py", ".sh", ".bash", ".zsh", ".fish", ".pl", ".rb", ".lua", ".php",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".kt", ".kts", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs",
    ".scala", ".sql", ".tf", ".tfvars", ".hcl", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".vim", ".el", ".r", ".gradle", ".ipynb",
}

CODE_NAMES = {"Dockerfile", "Makefile", "Justfile", "Vagrantfile", ".gitignore",
              ".dockerignore", ".gitattributes", ".editorconfig"}

# The two bare quotes are deliberate: a line that opens with a string literal is
# where UI copy sits, and a label or error string is in scope. They also catch a
# quoted dict value, so the label may name a key rather than screen text.
COMMENT_MARKERS = ("#", "//", "/*", "*/", "*", "--", "<!--", '"""', "'''", '"', "'")

STRIP_TRAILING = ("*/", "-->", '"""', "'''")

QUOTED = re.compile(r"`[^`]*`|\"[^\"]*\"|'[^']*'")

FENCE = re.compile(r"^\s*(?:```|~~~)")

MAX_REPORTED = 20


def added_text(tool, tool_input):
    if tool == "Write":
        return [tool_input.get("content", "")]
    if tool == "Edit":
        return [tool_input.get("new_string", "")]
    if tool == "MultiEdit":
        return [e.get("new_string", "") for e in tool_input.get("edits", [])
                if isinstance(e, dict)]
    if tool == "NotebookEdit":
        return [tool_input.get("new_source", "")]
    return []


def comment_body(line):
    """The prose of a comment line, or None if the line is not a comment."""
    stripped = line.strip()
    if not stripped.startswith(COMMENT_MARKERS):
        return None
    for marker in sorted(COMMENT_MARKERS, key=len, reverse=True):
        if stripped.startswith(marker):
            stripped = stripped[len(marker):]
            break
    for tail in STRIP_TRAILING:
        if stripped.endswith(tail):
            stripped = stripped[: -len(tail)]
            break
    return stripped


def scan(text, prose_file):
    """(line, label, word) per hit, deduplicated."""
    hits = []
    seen = set()
    in_fence = False
    for line in text.splitlines():
        if prose_file:
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            body = line
        else:
            body = comment_body(line)
            if body is None:
                continue
        # A word inside backticks or quotes is being named, not used.
        spans = [m.span() for m in QUOTED.finditer(body)]
        for label, rule in RULES:
            for m in rule.finditer(body):
                if any(s <= m.start() and m.end() <= e for s, e in spans):
                    continue
                hit = (line.strip(), label, m.group(0))
                if hit in seen:
                    continue
                seen.add(hit)
                hits.append(hit)
    return hits


def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""

    if any(part in path for part in EXEMPT_PATHS):
        return 0

    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if ext in PROSE_EXT:
        prose_file = True
    elif ext in CODE_EXT or name in CODE_NAMES:
        prose_file = False
    else:
        return 0

    hits = []
    for text in added_text(tool, tool_input):
        if isinstance(text, str):
            hits.extend(scan(text, prose_file))
    if not hits:
        return 0

    print('banned-vocabulary hits in %s (inventories: cut-the-crap "Before '
          'sending"; annotations and ticket ids: earn-the-line):'
          % (path or "<unknown>"), file=sys.stderr)
    for line, label, word in hits[:MAX_REPORTED]:
        print('  "%s" (%s) -- %s' % (word, label, line), file=sys.stderr)
    if len(hits) > MAX_REPORTED:
        print("  ... and %d more" % (len(hits) - MAX_REPORTED), file=sys.stderr)
    print("The write landed; fix the flagged lines with an Edit, not a re-run "
          "of the write.", file=sys.stderr)
    print("Mood words (puffery, self-vouching, softener, throat-clearing, "
          "inflated verb, coding-assistant tic): replace with the property or "
          "the consequence.", file=sys.stderr)
    print("Participle tail: delete the tail or state the condition it stands "
          "for.", file=sys.stderr)
    print("Corrective framing, not-only framing: keep the affirmative half and "
          "delete the denial.", file=sys.stderr)
    print("Empty negation: name the property that rules the option out -- \"a "
          "single /32 splits only by port range\" -- or delete the line.",
          file=sys.stderr)
    print("Edit annotation: delete the line if it records what the file used to "
          "say; if the line describes current behaviour or the file's subject "
          "is history, say so and leave it.", file=sys.stderr)
    print("Session address: the reader was not in the conversation -- write "
          "the constraint the code must satisfy, or delete the line.",
          file=sys.stderr)
    print("Plan reference: a phase or step number resolves to nothing once the "
          "plan is gone -- name the constraint instead.", file=sys.stderr)
    print("Ticket id: move it to the commit message; if the sentence then says "
          "nothing, write the fact.", file=sys.stderr)
    print("Edit the flagged lines only. If a hit is the correct term in context "
          "-- a domain word, a vendor name -- say so in one line and move on; "
          "one rewrite attempt per hit, then stop. Do not edit this hook, its "
          "inventories or EXEMPT_PATHS to clear a hit, and do not rewrite "
          "unflagged lines; a re-flag on a line you already rewrote is the same "
          "hit.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Our own parse failure is not the model's problem.
        sys.exit(0)
