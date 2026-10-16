"""The heal agent's tools. None takes a path from the model; all file reads go through agent.guard."""
import base64
import re
from pathlib import Path

from agent.guard import check, safe_read

MAX_HITS = 10
CONTEXT = 300  # chars either side of a search hit

TOOLS = [
    {"name": "read_script", "description": "Return the script source with line numbers.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "search_dom",
     "description": "Case-insensitive substring search over the trimmed DOM captured at the failure. "
                    "Returns up to 10 hits with surrounding markup and the frame each hit is in.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}},
                      "required": ["query"], "additionalProperties": False}},
    {"name": "view_screenshot", "description": "Return the full-page screenshot taken at the failure.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "submit_diagnosis",
     "description": "Submit the diagnosis and end the attempt. Call exactly once, as the last call.",
     "strict": True,
     "input_schema": {
         "type": "object", "additionalProperties": False,
         "required": ["cause_category", "cause_detail", "failing_step", "evidence", "confidence", "patch",
                      "touches_data_write", "proposed_decision", "reasoning"],
         "properties": {
             "cause_category": {"type": "string", "enum": ["script", "site", "infra", "unknown"]},
             "cause_detail": {"type": "string", "enum": ["selector_changed", "popup_modal", "login_changed",
                                                         "slow_page", "site_down", "other"]},
             "failing_step": {"type": ["string", "null"]},
             "evidence": {"type": "array", "items": {"type": "string"}},
             "confidence": {"type": "number", "description": "0.0 to 1.0"},
             "patch": {"type": ["string", "null"], "description": "Unified diff against the script, or null"},
             "touches_data_write": {"type": "boolean"},
             "proposed_decision": {"type": "string", "enum": ["auto_apply", "escalate"]},
             "reasoning": {"type": "string", "description": "Plain text, under 200 words"},
         }}},
]


class Toolbox:
    def __init__(self, bundle_dir: Path, script_path: Path):
        self.bundle_dir, self.script_path = Path(bundle_dir), Path(script_path)
        self.roots = [self.bundle_dir, self.script_path.parent]
        check(self.script_path, self.roots)

    def run(self, name: str, args: dict):
        """Return tool_result content (str or list of blocks). Raises KeyError on an unknown tool."""
        return {"read_script": self.read_script, "search_dom": self.search_dom,
                "view_screenshot": self.view_screenshot}[name](**args)

    def read_script(self) -> str:
        lines = safe_read(self.script_path, self.roots).splitlines()
        return "\n".join(f"{i:4d}  {line}" for i, line in enumerate(lines, 1))

    def search_dom(self, query: str) -> str:
        path = self.bundle_dir / "dom.html"
        if not path.exists():
            return "No DOM was captured for this failure."
        dom = safe_read(path, self.roots)
        hits = [m.start() for m in re.finditer(re.escape(query), dom, re.IGNORECASE)]
        if not hits:
            return f"No match for {query!r}."
        out = [f"{len(hits)} match(es) for {query!r}; showing {min(len(hits), MAX_HITS)}."]
        for pos in hits[:MAX_HITS]:
            label_at = dom.rfind("<!-- frame ", 0, pos)
            label = dom[label_at:dom.find("-->", label_at) + 3] if label_at >= 0 else "<!-- frame unknown -->"
            out.append(f"{label}\n...{dom[max(0, pos - CONTEXT):pos + len(query) + CONTEXT]}...")
        return "\n\n".join(out)

    def view_screenshot(self):
        path = self.bundle_dir / "screenshot.png"
        if not path.exists():
            return "No screenshot was captured for this failure."
        data = base64.standard_b64encode(safe_read(path, self.roots, binary=True)).decode()
        return [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}]
