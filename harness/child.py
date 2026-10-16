"""One browser run of a script, optionally with an injected failure. Started by harness.run.

Loads the script from a file path (so a sandbox copy can run the same way), applies the variant
to the browser context, calls the script's entry function, and on an exception writes the bundle.
Prints one JSON line on stdout with the outcome.
"""
import argparse
import dataclasses
import importlib.util
import io
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from failures import injectors
from harness import bundle


class Tee(io.TextIOBase):
    """Pass stderr through and keep a copy, to read the scripts' step events back."""
    def __init__(self, real):
        self.real, self.copy = real, io.StringIO()

    def write(self, s):
        self.real.write(s)
        self.copy.write(s)
        return len(s)

    def flush(self):
        self.real.flush()


def failing_step(log: str) -> str | None:
    step = None
    for line in log.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("event") == "step_end" and ev.get("ok") is False:
            step = ev["step"]  # the first failing step_end is the innermost step that raised
            break
    return step


def load_entry(path: Path, entry: str):
    spec = importlib.util.spec_from_file_location(f"run_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, entry)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script-path", type=Path, required=True)
    ap.add_argument("--entry", required=True)
    ap.add_argument("--kwargs", required=True, help="JSON object passed to the entry function")
    ap.add_argument("--variant")
    ap.add_argument("--run-dir", type=Path, required=True)
    a = ap.parse_args()

    fn = load_entry(a.script_path, a.entry)
    tee = Tee(sys.stderr)
    sys.stderr = tee
    with sync_playwright() as p:
        context = p.chromium.launch().new_context()
        applied = injectors.apply(context, a.variant) if a.variant else None
        page = context.new_page()
        try:
            out = fn(page, **json.loads(a.kwargs))
        except Exception as e:
            step = failing_step(tee.copy.getvalue())
            bundle.write(page, a.run_dir, e, step)
            result = {"ok": False, "error_type": type(e).__name__,
                      "error": (str(e).splitlines() or [""])[0], "failing_step": step}
        else:
            result = {"ok": True, "output": dataclasses.asdict(out) if dataclasses.is_dataclass(out) else out}
    result["injector_unmatched"] = applied.unmatched() if applied else []
    print(json.dumps(result, default=str), file=sys.__stdout__, flush=True)


if __name__ == "__main__":
    main()
