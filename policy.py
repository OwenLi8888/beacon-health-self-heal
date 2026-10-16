"""Auto-apply vs escalate (PRD F11). Code, not prompt: the agent proposes, this decides.
Harness-only; the heal agent can neither read nor import this file."""
import ast

CONFIDENCE_MIN = 0.8
DIFF_LINES_MAX = 10


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
           script_passed: bool, oracle_passed: bool) -> str:
    if diag.cause_category in ("site", "infra"):
        return "reported"
    if diag.cause_category != "script":
        return "escalate"
    ok = (diag.confidence >= CONFIDENCE_MIN
          and diag.patch is not None and 0 < diff_lines <= DIFF_LINES_MAX
          and not diag.touches_data_write
          and not (set(touched) & writes_data_lines(original_source))
          and diag.proposed_decision == "auto_apply"
          and script_passed and oracle_passed)
    return "auto_apply" if ok else "escalate"
