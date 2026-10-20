# Scorecard: b20261020-001525-8bae

Agent v3, model claude-sonnet-5-5. Generated from logs/attempts.jsonl only.

## Timing and element matching (16% of Beacon failures)

| Metric | tm dev | tm holdout | em dev | em holdout |
|---|---|---|---|---|
| Heal rate (auto-applied, oracle pass / cases) | 100% (3 of 3; 95% CI 44% to 100%) | not run | 100% (3 of 3; 95% CI 44% to 100%) | not run |
| Final decision = expected / cases | 100% (3 of 3; 95% CI 44% to 100%) | not run | 100% (3 of 3; 95% CI 44% to 100%) | not run |
| Cause correct (script / cases) | 100% (3 of 3; 95% CI 44% to 100%) | not run | 100% (3 of 3; 95% CI 44% to 100%) | not run |
| cause_detail chosen (expected: timing / element_match from agent v3) | slow_page 3 | not run | other 3 | not run |
| Tries per heal | 1.00 (3 heals) | not run | 1.00 (3 heals) | not run |
| Attempts | 3 | not run | 3 | not run |
| Cost | $0.1155 | not run | $0.0703 | not run |

Bad-fix attempts by type (every attempt, applied or not; applied must be 0):

| Type | Rejected | Applied | Total |
|---|---|---|---|
| fixed_sleep | 0 | 0 | 0 of 6 attempts |
| positional_pick | 0 | 0 | 0 of 6 attempts |
| wrong_patient | 0 | 0 | 0 of 6 attempts |

## dev

Cases: 6 failures healed or handled, 0 where the injected run did not fail, 0 with an injector that matched nothing. Attempts: 6.

| Metric | Value |
|---|---|
| Heal rate (auto-applied, oracle pass / heal-able) | 100% (6 of 6; 95% CI 61% to 100%) |
| **Wrong-fix rate, caught in sandbox** (script pass, oracle fail / patched reruns) | 0% (0 of 6; 95% CI 0% to 39%) |
| Wrong fixes auto-applied (0 by construction: policy needs an oracle pass) | 0 |
| Non-script patch rate (cases with a patch applied / non-script cases) | n/a (0 of 0) |
| Escalation correctness (final decision = expected / cases) | 100% (6 of 6; 95% CI 61% to 100%) |
| Cause correct (script vs site/infra / cases) | 100% (6 of 6; 95% CI 61% to 100%) |
| Diagnosis accuracy (cause_detail = failure type / cases) | 0% (0 of 6; 95% CI 0% to 39%) |
| Tries per heal (mean attempts over heals) | 1.00 (6 heals) |
| Cost per heal | $0.0310 ($0.1858 / 6) |
| Total cost | $0.1858 |
| Non-script patches discarded by the harness | 0 |

Decision matrix (rows expected, columns final). `gave_up` = 3 failed attempts, handed to a human; it never matches an expected decision.

| expected \ final | auto_apply |
|---|---|
| auto_apply | 6 |

By variant:

| Variant | Truth | Expected | Cases | Final decisions | Attempts | Cost |
|---|---|---|---|---|---|---|
| em_01 | script | auto_apply | 3 | auto_apply 3 | 3 | $0.0703 |
| tm_01 | script | auto_apply | 3 | auto_apply 3 | 3 | $0.1155 |

## holdout

Not run.

# v1: original scope (from results/final/attempts.jsonl)

## v1 dev

Cases: 12 failures healed or handled, 0 where the injected run did not fail, 0 with an injector that matched nothing. Attempts: 12.

| Metric | Value |
|---|---|
| Heal rate (auto-applied, oracle pass / heal-able) | 100% (9 of 9; 95% CI 70% to 100%) |
| **Wrong-fix rate, caught in sandbox** (script pass, oracle fail / patched reruns) | 0% (0 of 9; 95% CI 0% to 30%) |
| Wrong fixes auto-applied (0 by construction: policy needs an oracle pass) | 0 |
| Non-script patch rate (cases with a patch applied / non-script cases) | 0% (0 of 3; 95% CI 0% to 56%) |
| Escalation correctness (final decision = expected / cases) | 100% (12 of 12; 95% CI 76% to 100%) |
| Cause correct (script vs site/infra / cases) | 100% (12 of 12; 95% CI 76% to 100%) |
| Diagnosis accuracy (cause_detail = failure type / cases) | 100% (12 of 12; 95% CI 76% to 100%) |
| Tries per heal (mean attempts over heals) | 1.00 (9 heals) |
| Cost per heal | $0.0337 ($0.3033 / 9) |
| Total cost | $0.3033 |
| Non-script patches discarded by the harness | 0 |

Decision matrix (rows expected, columns final). `gave_up` = 3 failed attempts, handed to a human; it never matches an expected decision.

| expected \ final | auto_apply | reported |
|---|---|---|
| auto_apply | 9 | 0 |
| reported | 0 | 3 |

By variant:

| Variant | Truth | Expected | Cases | Final decisions | Attempts | Cost |
|---|---|---|---|---|---|---|
| sc_01 | script | auto_apply | 3 | auto_apply 3 | 3 | $0.1016 |
| sc_03 | script | auto_apply | 3 | auto_apply 3 | 3 | $0.0726 |
| sc_04 | script | auto_apply | 3 | auto_apply 3 | 3 | $0.0738 |
| sd_01 | infra | reported | 3 | reported 3 | 3 | $0.0554 |

## v1 holdout

Cases: 3 failures healed or handled, 0 where the injected run did not fail, 0 with an injector that matched nothing. Attempts: 3.

| Metric | Value |
|---|---|
| Heal rate (auto-applied, oracle pass / heal-able) | 100% (3 of 3; 95% CI 44% to 100%) |
| **Wrong-fix rate, caught in sandbox** (script pass, oracle fail / patched reruns) | 0% (0 of 3; 95% CI 0% to 56%) |
| Wrong fixes auto-applied (0 by construction: policy needs an oracle pass) | 0 |
| Non-script patch rate (cases with a patch applied / non-script cases) | n/a (0 of 0) |
| Escalation correctness (final decision = expected / cases) | 100% (3 of 3; 95% CI 44% to 100%) |
| Cause correct (script vs site/infra / cases) | 100% (3 of 3; 95% CI 44% to 100%) |
| Diagnosis accuracy (cause_detail = failure type / cases) | 100% (3 of 3; 95% CI 44% to 100%) |
| Tries per heal (mean attempts over heals) | 1.00 (3 heals) |
| Cost per heal | $0.0266 ($0.0797 / 3) |
| Total cost | $0.0797 |
| Non-script patches discarded by the harness | 0 |

Decision matrix (rows expected, columns final). `gave_up` = 3 failed attempts, handed to a human; it never matches an expected decision.

| expected \ final | auto_apply |
|---|---|
| auto_apply | 3 |

By variant:

| Variant | Truth | Expected | Cases | Final decisions | Attempts | Cost |
|---|---|---|---|---|---|---|
| sc_02 | script | auto_apply | 3 | auto_apply 3 | 3 | $0.0797 |
