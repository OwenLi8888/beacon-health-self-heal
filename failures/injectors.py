"""Failure injector: applies a catalog variant to a Playwright BrowserContext via context.route.
No OpenEMR source is touched. Harness-only; the heal agent never reads this directory."""
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from playwright.sync_api import BrowserContext, Route

CATALOG = Path(__file__).with_name("catalog.yaml")

# Rewrites the attribute as soon as the parser inserts the element, before any script step can see it.
SET_ATTRIBUTE_JS = """(() => {
  const cfg = %s;
  if (!location.pathname.includes(cfg.url)) return;
  const fix = () => {
    for (const el of document.querySelectorAll(cfg.selector)) {
      if (el.getAttribute(cfg.attribute) === cfg.old) {
        el.setAttribute(cfg.attribute, cfg.new);
        window.__h();
      }
    }
  };
  new MutationObserver(fix).observe(document, {childList: true, subtree: true});
})();"""

# Detaches the table's data rows (2+ cells) as the parser inserts them and puts them back delay_ms after
# the first one was held: the header is there, the data isn't yet. With a `placeholder`, a one-cell
# loading row stands in for them; without one, nothing does (an invisible empty text node marks the spot).
DELAY_ROWS_JS = """(() => {
  const cfg = %s;
  if (!location.pathname.includes(cfg.url)) return;
  const held = [];
  let anchor = null, timer = null;
  const hold = () => {
    for (const row of document.querySelectorAll(cfg.selector + ' tr')) {
      if (row === anchor || row.querySelectorAll(':scope > td').length < 2) continue;
      if (!anchor) {
        if (cfg.placeholder) {
          anchor = document.createElement('tr');
          anchor.innerHTML = `<td colspan="${row.children.length}" class="text-center">${cfg.placeholder}</td>`;
        } else {
          anchor = document.createTextNode('');
        }
        row.before(anchor);
      }
      held.push(row);
      row.remove();
      window.__h();
    }
    if (held.length && !timer) {
      timer = setTimeout(() => { obs.disconnect(); anchor.after(...held); anchor.remove(); }, cfg.delay_ms);
    }
  };
  const obs = new MutationObserver(hold);
  obs.observe(document, {childList: true, subtree: true});
})();"""


def load_catalog() -> dict[str, dict]:
    variants = yaml.safe_load(CATALOG.read_text())["variants"]
    return {v["id"]: v for v in variants}


@dataclass
class Applied:
    """What the injector did during one run, so a no-op variant can't pass as a break."""
    variant: dict
    hits: dict[str, int] = field(default_factory=dict)

    def unmatched(self) -> list[str]:
        return [old for old, n in self.hits.items() if n == 0]


def apply(context: BrowserContext, variant_id: str) -> Applied:
    variant = load_catalog()[variant_id]
    inj = variant["injector"]
    applied = Applied(variant)

    if inj["kind"] == "rewrite":
        applied.hits = {r["old"]: 0 for r in inj["replace"]}

        def handler(route: Route) -> None:
            resp = route.fetch()
            body = resp.text()
            for r in inj["replace"]:
                n = body.count(r["old"])
                applied.hits[r["old"]] += n
                body = body.replace(r["old"], r["new"])
            route.fulfill(response=resp, body=body)

        context.route(lambda url: inj["url"] in url, handler)
    elif inj["kind"] == "set_attribute":
        # For pages reached by redirect, which context.route never sees (e.g. main.php after login).
        key = f"{inj['selector']}[{inj['attribute']}]"
        applied.hits = {key: 0}

        def hit() -> None:
            applied.hits[key] += 1

        context.expose_function("__h", hit)
        context.add_init_script(SET_ATTRIBUTE_JS % json.dumps(inj))
    elif inj["kind"] == "delay_rows":
        key = f"{inj['selector']} rows"
        applied.hits = {key: 0}

        def hit() -> None:
            applied.hits[key] += 1

        context.expose_function("__h", hit)
        context.add_init_script(DELAY_ROWS_JS % json.dumps(inj))
    elif inj["kind"] == "duplicate_row":
        key = json.dumps(inj["match"])
        applied.hits = {key: 0}

        def handler(route: Route) -> None:
            resp = route.fetch()
            data = json.loads(resp.text())
            rows = [r for r in data["aaData"] if all(r.get(k) == v for k, v in inj["match"].items())]
            if rows:  # a copy of the real row, so the markup is the same; only `overrides` differ
                data["aaData"].insert(0, {**rows[0], **inj["overrides"]})
                data["iTotalDisplayRecords"] = int(data["iTotalDisplayRecords"]) + 1
                applied.hits[key] += 1
            route.fulfill(response=resp, body=json.dumps(data))

        context.route(lambda url: inj["url"] in url, handler)
    elif inj["kind"] == "status":
        applied.hits = {"<any request>": 0}

        def handler(route: Route) -> None:
            applied.hits["<any request>"] += 1
            route.fulfill(status=inj["status"], content_type="text/html", body=inj["body"])

        context.route(lambda url: inj["url"] in url, handler)
    else:
        raise ValueError(f"unknown injector kind {inj['kind']!r} in variant {variant_id}")
    return applied
