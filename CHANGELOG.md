# Changelog

Agent versions and their numbers. The agent is the prompt (`agent/prompt.md`), the tools (`agent/tools.py`) and the policy (`policy.py`).

## v3 (20 Oct 2026), the one tuning round on `feature/failure-mix`, frozen

**Dev batch** `b20261020-001525-8bae` (claude-sonnet-5-5, tm_01 + em_01 × 3), frozen at `ce1af86` (`results/v2/FROZEN.txt`):
- heal rate 6 of 6, 1.00 tries per heal
- bad fixes 0 of 6 attempts
- $0.1858 total

The tm_01 fix now waits for the data: `expect(<date cells>).not_to_have_count(0)`, where v2 waited for "Loading results…" to hide. Two findings were kept as findings, not tuned, so the holdout result means something:
- **`expect()` defaults to a 5 s timeout and tm_02 delays 6 s.** The dev fix shape may fail tm_02's rerun, which is what the holdout should show. The B2 report flagged this risk. A `locator.wait_for()` (30 s) would not have it.
- **The new `cause_detail` values went unused.** The agent still picked `slow_page` (tm) and `other` (em) in 6 of 6, so diagnosis accuracy is 0 of 6. The prompt never describes the values, so the schema alone didn't move the choice.

**Holdout, run once** `b20261020-003223-e88e` (tm_02 + em_02 × 3): heal rate 1 of 6, wrong fixes 0, bad fixes 0 of 6 attempts, $0.2242.
- **tm_02, 0 of 3.** All three were `unknown`/escalate with no patch. With no loading indicator, the failure snapshot shows only an empty table, and the agent read it as missing data, not timing. So the `expect()` 5 s timeout was never tested.
- **em_02, 1 of 3.** All three wrote the name + DOB patch, and all three reruns passed the oracle. One auto-applied. One escalated in policy (confidence 0.75 < 0.8). One was proposed as escalate by the agent ("a human should confirm the requested DOB is the intended patient").

- **Schema:** `cause_detail` gets `timing` and `element_match`. Under v2 the agent had to pick `slow_page` (tm) or `other` (em), so diagnosis accuracy couldn't be measured.
- **Prompt:** one sentence: "Wait for the data you need to read, not for a loading indicator to disappear."
- **Why:** the v2 dev batch `b20261019-235227-171f` healed 6 of 6, with 0 bad fixes and $0.17 spent. But all 3 tm_01 patches waited for the injected "Loading results…" text to be hidden. That passes tm_01, but it is tied to that one indicator. tm_02 was redesigned in the same round to have no indicator (see DECISIONS.md), so that kind of fix now fails the holdout.

## v2 (19 Oct 2026), on `feature/failure-mix`

Pivot v0.4 (timing and element matching):
- Policy: a fixed sleep (`sleep(`, `wait_for_timeout(`) is `rejected_bad_fix`. A positional pick (`.first`, `.last`, `.nth(`, `[n]`) is also `rejected_bad_fix` when the failure was a multiple match.
- Prompt: two sentences. Timing → wait for the specific element or data. Multiple match → tell them apart by stable data, never by position.

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
