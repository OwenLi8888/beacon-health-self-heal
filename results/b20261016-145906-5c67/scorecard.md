# Scorecard: b20261016-145906-5c67

Agent v1, model claude-sonnet-5-5. Generated from logs/attempts.jsonl only.

## dev

Not run.

## holdout

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
