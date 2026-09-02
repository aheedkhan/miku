---
name: adr-decisions
description: >-
  Architecture Decision Records for long-lived choices (FYP, lab tooling,
  agent profile). Use when locking a design, recording why, or revisiting an
  old decision. Complements FYP 14 — does not override it.
---

# ADR decisions

## Goal
Capture **why** we chose X over Y so future-you (and Miku) don't re-litigate forever.

## When to use
- "Let's lock this approach"
- Tooling choices (SearXNG, Ollama model default, build wrappers)
- Lab architecture that isn't already in FYP `14`
- Reversing a prior decision

## FYP rule
For FYP platform architecture, **`architecture/14-locked-architecture.md` wins**. Raise a CR / note conflict — don't silently contradict `14`. ADRs here are for agent_dev / lab / peripheral choices, or to *point at* an FYP decision with a short pointer.

## File location
`workspace/decisions/ADR-NNN-short-slug.md` (increment NNN)

## Template
```markdown
# ADR-NNN: <Title>
- Status: proposed | accepted | superseded by ADR-XXX
- Date: YYYY-MM-DD
- Deciders: aheedi (+ Miku notes)

## Context
What forces us to choose?

## Decision
What we will do.

## Alternatives considered
1. — why not
2. — why not

## Consequences
- Positive:
- Negative / risks:
- Follow-ups:

## Links
- PROGRESS / 14 / issues / PRs
```

## Habits
- One decision per ADR
- Prefer "accepted" only after it's actually in use
- When superseded, leave the old file and point forward
