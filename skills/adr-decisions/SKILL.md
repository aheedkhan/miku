---
name: adr-decisions
description: >-
  Architecture Decision Records for long-lived choices (lab tooling, agent
  profile, build wrappers). Use when locking a design, recording why, or
  revisiting an old decision.
---

# ADR decisions

## Goal
Capture **why** we chose X over Y so future-you (and Miku) don't re-litigate forever.

## When to use
- "Let's lock this approach"
- Tooling choices (SearXNG, Ollama model default, build wrappers)
- Lab architecture decisions
- Reversing a prior decision

## File location
`workspace/decisions/ADR-NNN-short-slug.md` (increment NNN)

## Template
```markdown
# ADR-NNN: <Title>
- Status: proposed | accepted | superseded by ADR-XXX
- Date: YYYY-MM-DD
- Deciders: user (+ Miku notes)

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
- issues / PRs / related notes
```

## Habits
- One decision per ADR
- Prefer "accepted" only after it's actually in use
- When superseded, leave the old file and point forward
