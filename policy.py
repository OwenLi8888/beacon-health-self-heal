"""Auto-apply vs escalate (PRD F11). Code, not prompt: the agent proposes, this decides.
Harness-only; the heal agent can neither read nor import this file."""
import ast
import re

CONFIDENCE_MIN = 0.8
DIFF_LINES_MAX = 10

FIXED_SLEEP = re.compile(r"\bsleep\s*\(|wait_for_timeout\s*\(")
POSITIONAL_PICK = re.compile(r"\.first\b|\.last\b|\.nth\s*\(|\[-?\d+\]")
MULTIPLE_MATCH = re.compile(r"^AmbiguousValue\b|strict mode violation")


def added_lines(patch: str) -> list[str]:
    return [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]


def bad_fix(patch: str, first_error: str | None) -> str | None:
    """A known-bad fix shape in the patch's added lines, or None. A positional pick is only bad when
    it resolves a multiple match; a timing fix may wait on `rows.first`."""
    added = "\n".join(added_lines(patch))
    if FIXED_SLEEP.search(added):
        return "fixed_sleep"
    if first_error and MULTIPLE_MATCH.search(first_error) and POSITIONAL_PICK.search(added):
        return "positional_pick"
    return None


def writes_data_lines(source: str) -> set[int]:
    """Line numbers inside functions decorated with @writes_data."""
    lines = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and any(
                (d.id if isinstance(d, ast.Name) else getattr(d, "attr", None)) == "writes_data"
                for d in node.decorator_list):
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])  # removing the mark counts
            lines.update(range(start, node.end_lineno + 1))
    return lines


def decide(diag, diff_lines: int, touched: list[int], original_source: str,
           script_passed: bool, oracle_passed: bool, *, first_error: str | None) -> str:
    if diag.cause_category in ("site", "infra"):
        return "reported"
    if diag.cause_category != "script":
        return "escalate"
    if diag.patch is not None and bad_fix(diag.patch, first_error):
        return "rejected_bad_fix"
    ok = (diag.confidence >= CONFIDENCE_MIN
          and diag.patch is not None and 0 < diff_lines <= DIFF_LINES_MAX
          and not diag.touches_data_write
          and not (set(touched) & writes_data_lines(original_source))
          and diag.proposed_decision == "auto_apply"
          and script_passed and oracle_passed)
    return "auto_apply" if ok else "escalate"
