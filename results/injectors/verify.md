# Injector verification (read_a1c; Rosa Delgado unless the variant pins a `patient`; DB reset before every run)

| Variant | Type | Split | Off (before) | On | Failing step | Expected step | Off (after) | dom.html KB | Error | Result |
|---|---|---|---|---|---|---|---|---|---|---|
| sc_01 | selector_changed | dev | pass | FAIL | search_patient | search_patient | pass | 18.2 | TimeoutError: Locator.fill: Timeout 30000ms exceeded. | ok |
| sc_02 | selector_changed | holdout | pass | FAIL | open_lab_results | open_lab_results | pass | 24.6 | TimeoutError: Locator.wait_for: Timeout 30000ms exceeded. | ok |
| sc_03 | selector_changed | dev | pass | FAIL | read_latest_a1c | read_latest_a1c | pass | 7.7 | TimeoutError: Locator.click: Timeout 30000ms exceeded. | ok |
| sc_04 | selector_changed | dev | pass | FAIL | read_latest_a1c | read_latest_a1c | pass | 9.6 | Error: Locator.wait_for: Error: strict mode violation: get_by_role("table").filter(has=locator("iframe[name='pat']").content_frame.get_by_role("columnheader", name="Result", exact=True)) resolved to 2 elements: | ok |
| sd_01 | site_down | dev | pass | FAIL | login | login | pass | 0.2 | TimeoutError: Locator.fill: Timeout 30000ms exceeded. | ok |
| tm_01 | timing | dev | pass | FAIL | read_latest_a1c | read_latest_a1c | pass | 8.5 | ValueNotFound: A1c result table has no rows | ok |
| tm_02 | timing | holdout | pass | FAIL | read_latest_a1c | read_latest_a1c | pass | 8.5 | ValueNotFound: A1c result table has no rows | ok |
| em_01 | element_matching | dev | pass | FAIL | search_patient | search_patient | pass | 10.6 | AmbiguousValue: 2 patients named Rosa Delgado | ok |
| em_02 | element_matching | holdout | pass | FAIL | search_patient | search_patient | pass | 10.4 | AmbiguousValue: 2 patients named Marcus Bell | ok |
