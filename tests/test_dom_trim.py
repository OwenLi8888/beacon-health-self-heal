from playwright.sync_api import sync_playwright

from harness.bundle import cap_chunks, trimmed_dom

PAGE = """<html><head><style>p{}</style><script>var secret=1</script></head><body>
<p id="keep" style="color:red" data-x="1">Visible   text</p>
<p style="display:none">Hidden text</p>
<input type="hidden" name="csrf" value="tok">
<select name="s"><option value="a">A</option><option value="b">B</option></select>
<button onclick="go()">Submit</button>
</body></html>"""


def test_trim_drops_scripts_styles_hidden_and_noise_attrs():
    with sync_playwright() as p:
        page = p.chromium.launch().new_page()
        page.set_content(PAGE)
        dom = trimmed_dom(page)
    assert '<p id="keep">Visible text</p>' in dom
    assert "Hidden text" not in dom and "csrf" not in dom
    assert "secret" not in dom and "p{}" not in dom
    assert '<option value="b">B</option>' in dom
    assert '<button onclick="go()">Submit</button>' in dom


def test_cap_cuts_largest_chunk_and_marks_it():
    out = cap_chunks([["<!-- a -->", "x" * 50_000], ["<!-- b -->", "y" * 100]], cap=30_000)
    assert len(out.encode()) <= 30_000
    assert "y" * 100 in out and "<!-- truncated" in out
