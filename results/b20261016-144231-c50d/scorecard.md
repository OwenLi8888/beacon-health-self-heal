# Scorecard: b20261016-144231-c50d

Agent v1, model claude-sonnet-5-5. Generated from logs/attempts.jsonl only.

## dev

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
| Tries per heal (mean attempts, 9 heals) | 1.00 |
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

## holdout

Not run.
