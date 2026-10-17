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
- 2 of the 3 sc_04 heals replaced a role locator with a CSS class (`table.border`). The third added a role-based `.filter(has_not=get_by_role("table"))`. All three pass, but the class version is more brittle and goes against the prompt's own "prefer role/label" rule. The same failure doesn't always get the same patch, and neither the policy nor the oracle checks locator quality.
- Confidences were 0.85 to 0.96 against a 0.8 auto-apply threshold. The lowest, 0.85 on all three sc_04 heals, was 0.05 above the line.
