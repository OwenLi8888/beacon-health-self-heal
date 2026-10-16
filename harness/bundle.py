"""Artifact bundle for a failed run: error, failing step, screenshot, trimmed DOM (+ full DOM).

The trimmed DOM is what the heal agent reads. OpenEMR renders its content in iframes, so every
visible frame is dumped under its own header; page.content() alone would miss the chart and labs.
"""
import json
import re
import traceback
from pathlib import Path

from playwright.sync_api import Frame, Page

DOM_CAP = 30_000  # bytes, see DECISIONS.md

# Walks the live DOM so hidden nodes can be judged by computed style, which a clone loses.
TRIM_JS = r"""
() => {
  const SKIP = new Set(["SCRIPT", "STYLE", "LINK", "NOSCRIPT", "TEMPLATE", "SVG", "META", "HEAD", "BASE"]);
  const VOID = new Set(["INPUT", "BR", "HR", "IMG", "COL", "WBR", "AREA", "SOURCE", "TRACK", "EMBED"]);
  const KEEP = new Set(["id", "class", "name", "type", "value", "placeholder", "role", "href", "title",
                        "for", "alt", "checked", "selected", "disabled", "onclick", "colspan", "level"]);
  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const attrs = el => {
    let out = "";
    for (const a of el.attributes) {
      if (!KEEP.has(a.name) && !a.name.startsWith("aria-")) continue;
      let v = a.value.replace(/\s+/g, " ").trim();
      if (v.length > 120) v = v.slice(0, 120) + "...";
      out += v ? ` ${a.name}="${esc(v).replace(/"/g, "&quot;")}"` : ` ${a.name}`;
    }
    return out;
  };
  // Options of a closed <select> report as not rendered but are still choosable.
  const hidden = el => !el.closest("select") && !el.checkVisibility({visibilityProperty: true});
  const walk = node => {
    if (node.nodeType === Node.TEXT_NODE) {
      const t = node.textContent.replace(/\s+/g, " ");
      return t.trim() ? esc(t) : "";
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    const tag = node.tagName.toUpperCase();
    if (SKIP.has(tag) || (tag !== "HTML" && tag !== "BODY" && hidden(node))) return "";
    const name = tag.toLowerCase();
    if (tag === "IFRAME") return `<iframe${attrs(node)}></iframe>`;  // contents dumped per frame
    if (VOID.has(tag)) return `<${name}${attrs(node)}>`;
    let inner = "";
    for (const c of node.childNodes) inner += walk(c);
    return `<${name}${attrs(node)}>${inner}</${name}>`;
  };
  return walk(document.documentElement);
}
"""


def _frame_label(frame: Frame) -> str:
    name = "top" if frame.parent_frame is None else (frame.frame_element().get_attribute("name") or "")
    url = re.sub(r"(token_main|csrf_token_form)=[^&]*", r"\1=REDACTED", frame.url)  # session tokens
    return f"<!-- frame name={name!r} url={url} -->"


def _visible_frames(page: Page) -> list[Frame]:
    """Top document plus every child frame whose <iframe> element is visible (the open tab)."""
    frames = [page.main_frame]
    for f in page.frames[1:]:
        try:
            if f.frame_element().is_visible():
                frames.append(f)
        except Exception:  # frame detached mid-capture
            continue
    return frames


def trimmed_dom(page: Page, cap: int = DOM_CAP) -> str:
    chunks = []
    for f in _visible_frames(page):
        try:
            chunks.append([_frame_label(f), f.evaluate(TRIM_JS)])
        except Exception as e:
            chunks.append([_frame_label(f), f"<!-- frame not readable: {type(e).__name__} -->"])
    return cap_chunks(chunks, cap)


def cap_chunks(chunks: list[list[str]], cap: int) -> str:
    """Join [label, body] chunks; while over cap, cut the largest body and mark the cut."""
    def total() -> int:
        return sum(len((label + "\n" + body + "\n").encode()) for label, body in chunks)
    while total() > cap:
        biggest = max(chunks, key=lambda c: len(c[1].encode()))
        over = total() - cap
        keep = max(0, len(biggest[1].encode()) - over - 64)
        cut = len(biggest[1].encode()) - keep
        biggest[1] = biggest[1].encode()[:keep].decode(errors="ignore") + f"<!-- truncated {cut} bytes -->"
        if keep == 0:  # only labels and markers left; nothing more to cut
            break
    return "".join(f"{label}\n{body}\n" for label, body in chunks)


def full_dom(page: Page) -> str:
    out = []
    for f in page.frames:
        try:
            out.append(f"{_frame_label(f)}\n{f.content()}\n")
        except Exception as e:
            out.append(f"<!-- frame {f.url} not readable: {type(e).__name__} -->\n")
    return "".join(out)


def write(page: Page, run_dir: Path, exc: BaseException, step: str | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "error.json").write_text(json.dumps({
        "error_type": type(exc).__name__,
        "message": str(exc),
        "failing_step": step,
        "traceback": "".join(traceback.format_exception(exc)),
    }, indent=2))
    page.screenshot(path=run_dir / "screenshot.png", full_page=True)
    (run_dir / "dom.html").write_text(trimmed_dom(page))
    (run_dir / "dom_full.html").write_text(full_dom(page))
