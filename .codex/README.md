# Codex Worker Notes for c-ross-2

This directory records the local Codex worker convention for this repo.

Start every worker run with:

```bash
git status --short --branch
```

Then read:

1. `AGENTS.md`
2. `.hermes/project-status.md`
3. The active plan under `docs/plans/`

Do not commit, push, or open PRs without explicit approval when you are acting as a standalone Codex CLI worker. In this repo, `AGENTS.md` is the authoritative workflow for Hermes/project-agent runs after user authorization; the Hermes controller may automatically commit, push, or open/update a PR on that approved scope while Codex CLI workers still honor this local approval boundary for their own direct actions.
