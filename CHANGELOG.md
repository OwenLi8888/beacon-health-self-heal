# Changelog

Agent versions and their numbers. The agent is the prompt (`agent/prompt.md`), the tools (`agent/tools.py`) and the policy (`policy.py`).

## v1 (16 Oct 2026), frozen

The first version: the tools, the F6 schema, 3 attempts × 8 tool calls, and the policy (cause = script, confidence ≥ 0.8, diff ≤ 10 lines, rerun and oracle pass).

**Dev batch** `b20261016-144231-c50d` (claude-sonnet-5-5, 4 variants × 3 repeats):
- heal rate 9 of 9
- wrong fixes 0 of 9 patched reruns
- non-script patches 0 of 3
- correct final decision 12 of 12
- 1.00 tries per heal, $0.0337 per heal, $0.30 total

**Tuning round: no change.** The miss review (block 4, step 1) found 0 misses in 12 attempts, so no bucket needed fixing, and v1 was kept rather than bumped to v2. Near-misses, kept as findings rather than fixed, so the holdout result means something:
- The sc_04 heal replaced a role locator with a CSS class (`table.border`). It passes, but it is more brittle than the original and goes against the prompt's own "prefer role/label" rule. Neither the policy nor the oracle checks locator quality.
- Confidences were 0.85 to 0.96 against a 0.8 auto-apply threshold.
