# Injector verification (read_a1c, Rosa Delgado, DB reset before every run)

| Variant | Type | Split | Off (before) | On | Failing step | Expected step | Off (after) | dom.html KB | Error | Result |
|---|---|---|---|---|---|---|---|---|---|---|
| sc_01 | selector_changed | dev | pass | FAIL | search_patient | search_patient | pass | 18.2 | TimeoutError: Locator.fill: Timeout 30000ms exceeded. | ok |
| sc_02 | selector_changed | holdout | pass | FAIL | open_lab_results | open_lab_results | pass | 24.6 | TimeoutError: Locator.wait_for: Timeout 30000ms exceeded. | ok |
| sc_03 | selector_changed | dev | pass | FAIL | read_latest_a1c | read_latest_a1c | pass | 7.7 | TimeoutError: Locator.click: Timeout 30000ms exceeded. | ok |
| sc_04 | selector_changed | dev | pass | FAIL | read_latest_a1c | read_latest_a1c | pass | 9.6 | Error: Locator.wait_for: Error: strict mode violation: get_by_role("table").filter(has=locator("iframe[name='pat']").content_frame.get_by_role("columnheader", name="Result", exact=True)) resolved to 2 elements: | ok |
| sd_01 | site_down | dev | pass | FAIL | login | login | pass | 0.2 | TimeoutError: Locator.fill: Timeout 30000ms exceeded. | ok |
