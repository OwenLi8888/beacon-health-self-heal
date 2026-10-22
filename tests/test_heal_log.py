"""Per-heal log files: the agent loop records a transcript, and the harness writes one file per heal."""
import json
from types import SimpleNamespace

from agent import heal as agent_heal
from harness import heal as harness_heal

SITE_DOWN = dict(cause_category="site", cause_detail="site_down", failing_step="login",
                 evidence=["Screenshot shows a 502 page"], confidence=0.95, patch=None,
                 touches_data_write=False, proposed_decision="escalate", reasoning="The site is down.")


def _usage():
    return SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0,
                           cache_creation_input_tokens=0)


def _use(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


class FakeClient:
    """Answers read_script first, then submit_diagnosis, and records what it was sent."""

    def __init__(self):
        self.turns = [[SimpleNamespace(type="text", text="Reading the script."), _use("t1", "read_script", {})],
                      [_use("t2", "submit_diagnosis", SITE_DOWN)]]
        self.sent = []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.sent.append(kw["messages"])
        return SimpleNamespace(content=self.turns.pop(0), usage=_usage())


def test_transcript_records_brief_calls_results_and_submit(tmp_path):
    (tmp_path / "error.json").write_text(json.dumps({"error_type": "TimeoutError", "message": "Locator.fill",
                                                     "failing_step": "login"}))
    sandbox = tmp_path / "sandbox" / "s.py"
    sandbox.parent.mkdir()
    sandbox.write_text("page.fill('#authUser', user)\n")
    client = FakeClient()

    usage, diag = agent_heal._diagnose(client, "claude-sonnet-5-5", tmp_path, sandbox, None)

    assert diag.cause_detail == "site_down"
    t = usage["transcript"]
    assert t[0]["kind"] == "brief" and "Failing step: login" in t[0]["text"]
    assert t[1]["kind"] == "assistant" and t[1]["blocks"][1] == {"type": "tool_use", "name": "read_script", "input": {}}
    assert t[1]["usage"]["cost_usd"] > 0
    assert t[2]["kind"] == "tool_results" and "page.fill('#authUser', user)" in t[2]["results"][0]["content"]
    assert t[3]["blocks"][0]["name"] == "submit_diagnosis"
    json.dumps(t)
    assert all(set(m) == {"role", "content"} for m in client.sent[-1])  # a record only, never sent back


def test_write_heal_log_one_file_per_heal(tmp_path, monkeypatch):
    monkeypatch.setattr(harness_heal, "HEALS", tmp_path / "heals")
    joined = {"heal_id": "20261022-000000-abcd", "variant": "x", "truth_cause": "script"}
    attempts = [{"attempt": 1, "decision": "escalate", "final_decision": "escalate", "cost_usd": 0.01,
                 "transcript": [{"kind": "brief", "text": "The script failed."}]}]

    path = harness_heal.write_heal_log(joined, attempts, None)

    assert path == tmp_path / "heals" / "20261022-000000-abcd.json"
    assert list((tmp_path / "heals").iterdir()) == [path]
    log = json.loads(path.read_text())
    assert log["approved_diff"] is None and log["attempts_used"] == 1 and log["final_decision"] == "escalate"
    assert log["attempts"][0]["transcript"][0]["kind"] == "brief"
