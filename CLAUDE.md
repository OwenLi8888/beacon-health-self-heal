# Beacon self-healing Playwright scripts (take-home)

Read docs/BEACON_BRD_PRD.md (the spec) and docs/BEACON_HIRING_CONTEXT.md (why) before any work.
Environment: WSL2 Ubuntu 26.04, Docker Desktop, Python via uv. Work only inside this repo.

## Rules
- Follow the build order in PRD section B12. One step at a time; stop and summarize when a step is done.
- The agent must never read or edit oracle/, failures/, policy.py, or logs/. Enforce in code.
- Never weaken assertions or the oracle to make something pass.
- Scripts raise on missing or unparseable values. No defaults, no invented values.
- Smallest diff that works. No retry or self-healing logic inside scripts.
- Log tokens and cost on every model call.
- After each non-obvious choice, add 2 to 3 lines to DECISIONS.md: options, choice, cost.
- Never print or commit secrets. ANTHROPIC_API_KEY lives only in .env.


