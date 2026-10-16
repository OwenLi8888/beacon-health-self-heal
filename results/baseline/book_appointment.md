# book_appointment baseline

19/20 runs passed the oracle (DB reset before each run; 5 cases rotated, listed in harness/baseline.py).
Mean script time: 6.9s. Per-run detail: book_appointment.jsonl.

Known flake: run 8 (Elena Delgado, New Patient, 2026-11-05 14:15) timed out in ;
Save was clicked but the dialog never closed and nothing was written, so it failed safely.
Not reproduced in 25 further runs of that case, or in 6 runs at 20x CPU throttling. About 1 in 77
S2 runs overall. Cause unknown; to be diagnosed with Session B failure bundles.
