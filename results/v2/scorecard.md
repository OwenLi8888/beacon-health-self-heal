# Scorecard: b20261020-001525-8bae, b20261020-003223-e88e

Agent v3, model claude-sonnet-5-5. Generated from logs/attempts.jsonl only.

## Dev vs holdout

| Metric | Dev | Holdout |
|---|---|---|
| Heal rate (auto-applied, oracle pass / heal-able) | 100% (6 of 6; 95% CI 61% to 100%) | 17% (1 of 6; 95% CI 3% to 56%) |
| **Wrong-fix rate, caught in sandbox** (script pass, oracle fail / patched reruns) | 0% (0 of 6; 95% CI 0% to 39%) | 0% (0 of 3; 95% CI 0% to 56%) |
| Wrong fixes auto-applied (0 by construction: policy needs an oracle pass) | 0 | 0 |
| Non-script patch rate (cases with a patch applied / non-script cases) | n/a (0 of 0) | n/a (0 of 0) |
| Escalation correctness (final decision = expected / cases) | 100% (6 of 6; 95% CI 61% to 100%) | 17% (1 of 6; 95% CI 3% to 56%) |
| Cause correct (script vs site/infra / cases) | 100% (6 of 6; 95% CI 61% to 100%) | 50% (3 of 6; 95% CI 19% to 81%) |
| Diagnosis accuracy (cause_detail = failure type / cases) | 0% (0 of 6; 95% CI 0% to 39%) | 0% (0 of 6; 95% CI 0% to 39%) |
| Tries per heal (mean attempts over heals) | 1.00 (6 heals) | 1.00 (1 heals) |
| Cost per heal | $0.0310 ($0.1858 / 6) | $0.2242 ($0.2242 / 1) |
| Total cost | $0.1858 | $0.2242 |
| Non-script patches discarded by the harness | 0 | 0 |

## Timing and element matching (16% of Beacon failures)

| Metric | tm dev | tm holdout | em dev | em holdout |
|---|---|---|---|---|
| Heal rate (auto-applied, oracle pass / cases) | 100% (3 of 3; 95% CI 44% to 100%) | 0% (0 of 3; 95% CI 0% to 56%) | 100% (3 of 3; 95% CI 44% to 100%) | 33% (1 of 3; 95% CI 6% to 79%) |
| Final decision = expected / cases | 100% (3 of 3; 95% CI 44% to 100%) | 0% (0 of 3; 95% CI 0% to 56%) | 100% (3 of 3; 95% CI 44% to 100%) | 33% (1 of 3; 95% CI 6% to 79%) |
| Cause correct (script / cases) | 100% (3 of 3; 95% CI 44% to 100%) | 0% (0 of 3; 95% CI 0% to 56%) | 100% (3 of 3; 95% CI 44% to 100%) | 100% (3 of 3; 95% CI 44% to 100%) |
| cause_detail chosen (expected: timing / element_match from agent v3) | slow_page 3 | other 3 | other 3 | other 3 |
| Tries per heal | 1.00 (3 heals) | n/a (0 heals) | 1.00 (3 heals) | 1.00 (1 heals) |
| Attempts | 3 | 3 | 3 | 3 |
| Cost | $0.1155 | $0.1537 | $0.0703 | $0.0705 |

Bad-fix attempts by type (every attempt, applied or not; applied must be 0):

| Type | Rejected | Applied | Total |
|---|---|---|---|
| fixed_sleep | 0 | 0 | 0 of 12 attempts |
| positional_pick | 0 | 0 | 0 of 12 attempts |
| wrong_patient | 0 | 0 | 0 of 12 attempts |

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

Cases: 6 failures healed or handled, 0 where the injected run did not fail, 0 with an injector that matched nothing. Attempts: 6.

| Metric | Value |
|---|---|
| Heal rate (auto-applied, oracle pass / heal-able) | 17% (1 of 6; 95% CI 3% to 56%) |
| **Wrong-fix rate, caught in sandbox** (script pass, oracle fail / patched reruns) | 0% (0 of 3; 95% CI 0% to 56%) |
| Wrong fixes auto-applied (0 by construction: policy needs an oracle pass) | 0 |
| Non-script patch rate (cases with a patch applied / non-script cases) | n/a (0 of 0) |
| Escalation correctness (final decision = expected / cases) | 17% (1 of 6; 95% CI 3% to 56%) |
| Cause correct (script vs site/infra / cases) | 50% (3 of 6; 95% CI 19% to 81%) |
| Diagnosis accuracy (cause_detail = failure type / cases) | 0% (0 of 6; 95% CI 0% to 39%) |
| Tries per heal (mean attempts over heals) | 1.00 (1 heals) |
| Cost per heal | $0.2242 ($0.2242 / 1) |
| Total cost | $0.2242 |
| Non-script patches discarded by the harness | 0 |

Decision matrix (rows expected, columns final). `gave_up` = 3 failed attempts, handed to a human; it never matches an expected decision.

| expected \ final | auto_apply | escalate |
|---|---|---|
| auto_apply | 1 | 5 |

By variant:

| Variant | Truth | Expected | Cases | Final decisions | Attempts | Cost |
|---|---|---|---|---|---|---|
| em_02 | script | auto_apply | 3 | auto_apply 1, escalate 2 | 3 | $0.0705 |
| tm_02 | script | auto_apply | 3 | escalate 3 | 3 | $0.1537 |

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
