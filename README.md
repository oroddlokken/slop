# Slop

Various slop I have made for use with Claude Code or OpenCode.

[claude](claude) is the tooling I run inside Claude Code itself: the status line, `ccreport` cost reporting in USD and NOK, and a hook that blocks `git stash` and `git worktree`. The rest below are skills.

[audit-agent-docs](audit-agent-docs) and [codehealth](codehealth) are skills I use often to keep vibe coded projects somewhat maintainable.

[should-i-abstract](should-i-abstract) is a pragmatic DRY review that finds both under-DRY and over-DRY code — flagging true duplication worth consolidating and wrong abstractions worth inlining.

[comment-cop](comment-cop) reviews the prose layer instead of the logic — stale comments, rambling, LLM filler, and the places where the missing *why* would have saved someone. [string-cop](string-cop) does the same for the strings the user actually reads — copy that contradicts the screen, reassures about nothing, or lectures where a number would do.

[perf-cop](perf-cop) is the runtime-cost sweep — parallel agents hunting hot loops, chatty I/O, blocking calls and cold-start weight, where every finding has to name the workload it costs or it gets demoted.

[dba](dba) is a database & SQL deep-dive — parallel agents scanning through lenses like injection, N+1, schema drift, and transaction gaps, distilled into prioritized fixes.

[test-my-tests](test-my-tests) asks whether your tests would actually catch real bugs, not just whether they exist.

[fuzz-my-stuff-up](fuzz-my-stuff-up) throws hostile and malformed input at your code to find the crashes before your users do.

[write-agent-docs](write-agent-docs) and [audit-agent-docs](audit-agent-docs)' sibling [audit-agent-prompt](audit-agent-prompt) cover the agent-instructions side: writing CLAUDE.md/AGENTS.md-style docs, and auditing a production agent's system prompt. [write-agent-prompt](write-agent-prompt) is the authoring counterpart for system prompts, personas, and tool descriptions.

[ghostty](ghostty) is my terminal config.
