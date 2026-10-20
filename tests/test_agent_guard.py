"""The heal agent can't reach ground truth or judges, and its patches apply by content."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import policy
from agent import patch
from agent.guard import REPO, check
from agent.tools import Toolbox

AGENT = REPO / "agent"


@pytest.fixture
def bundle(tmp_path):
    (tmp_path / "dom.html").write_text("<!-- frame name='top' url=x -->\n<button>Show results</button>\n")
    script = tmp_path / "sandbox" / "s.py"
    script.parent.mkdir()
    script.write_text("x = 1\n")
    return tmp_path, script


@pytest.mark.parametrize("target", ["oracle/s1_read_a1c.py", "failures/catalog.yaml", "policy.py",
                                    "logs/attempts.jsonl", "results/injectors/verify.md"])
def test_denied_even_if_listed_as_allowed(target):
    with pytest.raises(PermissionError):
        check(REPO / target, [REPO])


def test_dotdot_and_symlink_escapes_denied(bundle, tmp_path):
    root, _ = bundle
    with pytest.raises(PermissionError):
        check(root / ".." / "elsewhere.txt", [root])
    link = root / "cat.yaml"
    link.symlink_to(REPO / "failures" / "catalog.yaml")
    with pytest.raises(PermissionError):
        check(link, [root])


def test_tools_read_bundle_and_sandbox(bundle):
    root, script = bundle
    box = Toolbox(root, script)
    assert "x = 1" in box.read_script()
    assert "Show results" in box.search_dom("show RESULTS")
    assert "frame name='top'" in box.search_dom("button")


def test_agent_never_imports_judges():
    banned = {"failures", "oracle", "policy", "harness", "scripts"}
    for f in AGENT.glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not {n.split(".")[0] for n in names} & banned, f"{f.name} imports {names}"


SRC = "def a():\n    b = page.get_by_role('button', name='Submit')\n    b.click()\n"


def test_patch_ignores_wrong_hunk_header():
    diff = ("--- a/s.py\n+++ b/s.py\n@@ -40,3 +40,3 @@\n def a():\n"
            "-    b = page.get_by_role('button', name='Submit')\n+    b = page.get_by_role('button', name='Show results')\n")
    out = patch.apply(SRC, diff)
    assert "Show results" in out and "Submit" not in out
    assert patch.changed_lines(SRC, out) == (2, [2])


def test_patch_rejects_unmatched_context():
    with pytest.raises(patch.PatchError):
        patch.apply(SRC, "@@ -1 +1 @@\n-nope\n+yes\n")


def _diag(**kw):
    base = dict(cause_category="script", confidence=0.9, patch="x", touches_data_write=False,
                proposed_decision="auto_apply")
    return SimpleNamespace(**{**base, **kw})


def test_policy():
    src = "@step\n@writes_data\ndef save():\n    pass\n\ndef read():\n    pass\n"
    assert policy.decide(_diag(), 2, [7], src, True, True, first_error=None) == "auto_apply"
    assert policy.decide(_diag(cause_category="infra"), 0, [], src, False, False, first_error=None) == "reported"
    assert policy.decide(_diag(confidence=0.7), 2, [7], src, True, True, first_error=None) == "escalate"
    assert policy.decide(_diag(), 11, [7], src, True, True, first_error=None) == "escalate"
    assert policy.decide(_diag(), 2, [4], src, True, True, first_error=None) == "escalate"  # inside @writes_data
    assert policy.decide(_diag(), 2, [7], src, True, False, first_error=None) == "escalate"
    assert policy.decide(_diag(), 1, [2], src, True, True, first_error=None) == "escalate"  # deleting @writes_data itself
    assert policy.decide(_diag(cause_category="unknown"), 0, [], src, False, False, first_error=None) == "escalate"


def _row(run_id, attempt, decision, final, **kw):
    base = dict(run_id=run_id, heal_id=run_id, batch_id="b1", attempt=attempt, decision=decision,
                final_decision=final, is_final=final is not None, split="dev", variant="sc_03",
                failure_type="selector_changed", truth_cause="script", expected_decision="auto_apply",
                patch_applied=True, patch_discarded=False, script_passed=True, oracle_passed=True,
                cost_usd=0.01, model="m", agent_version="v1", injector_unmatched=[],
                agent_output={"cause_category": "script", "cause_detail": "selector_changed"})
    return {**base, **kw}


def test_scorecard_from_rows():
    from scorecard.score import section
    rows = [_row("r1", 1, "rerun_failed", None, oracle_passed=False),  # wrong fix caught in sandbox
            _row("r1", 2, "auto_apply", "auto_apply"),
            _row("r2", 1, "reported", "reported", variant="sd_01", failure_type="site_down", truth_cause="infra",
                 expected_decision="reported", patch_applied=False, script_passed=None, oracle_passed=None,
                 agent_output={"cause_category": "infra", "cause_detail": "site_down"})]
    text = "\n".join(section("dev", rows))
    assert "100% (1 of 1;" in text  # heal rate
    assert "50% (1 of 2;" in text  # wrong-fix caught in sandbox
    assert "0% (0 of 1;" in text  # non-script patch rate


def test_flaky_section_counts_bad_fixes():
    from scorecard.score import flaky_section
    em = dict(variant="em_01", failure_type="element_matching")
    rows = [_row("t1", 1, "rejected_bad_fix", "rejected_bad_fix", variant="tm_01", failure_type="timing",
                 bad_fix_type="fixed_sleep"),
            _row("e1", 1, "rerun_failed", None, oracle_passed=False, bad_fix_type="positional_pick", **em),  # wrong chart
            _row("e1", 2, "auto_apply", "auto_apply", **em)]
    text = "\n".join(flaky_section(rows))
    assert "| fixed_sleep | 1 | 0 | 1 of 3 attempts |" in text
    assert "| positional_pick | 1 | 0 | 1 of 3 attempts |" in text
    assert "| wrong_patient | 1 | 0 | 1 of 3 attempts |" in text
    assert "0% (0 of 1;" in text and "100% (1 of 1;" in text  # tm dev heal rate, em dev heal rate
