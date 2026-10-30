"""markdown.js (SPEC-0005, ADR-0005 point 5): the subset renders as DOM, everything else stays literal text."""
from __future__ import annotations

from .conftest import ROOT

RENDER = """async ([md]) => {
  const { render } = await import('/static/markdown.js');
  const { h } = await import('/static/dom.js');
  const before = document.scripts.length;
  const host = document.createElement('div');
  host.append(render(md, h));
  document.body.append(host);
  window.__host = host;
  return { text: host.textContent, scripts: document.scripts.length - before };
}"""


def run(page, md):
    return page.evaluate(RENDER, [md])


def count(page, selector):
    return page.evaluate("(s) => window.__host.querySelectorAll(s).length", selector)


def open_blank(open_page):
    return open_page("view=work&data=sample-company&motion=reduce", wait="article.report")


def test_fixture_report_renders_and_demotes_headings(open_page):
    page = open_blank(open_page)
    md = (ROOT.parents[2] / "tests" / "viz" / "fixtures" / "sample-company" / "reports" / "cycle-001.md").read_text(encoding="utf-8")
    run(page, md)
    assert page.evaluate("window.__host.querySelector('h2').textContent") == "Cycle 1 report"
    assert count(page, "h1") == 0
    assert count(page, "h3") >= 8
    assert count(page, "a") == 0  # the report has markdown links only to relative paths, which stay literal
    codes = page.evaluate("[...window.__host.querySelectorAll('code')].map(c => c.textContent)")
    assert "http://devbox:8000/app/" in codes
    assert not page.errors


def test_raw_html_is_literal(open_page):
    page = open_blank(open_page)
    out = run(page, "<script>alert(1)</script>\n\n<img src=x onerror=1>")
    assert out["scripts"] == 0
    assert "<script>alert(1)</script>" in out["text"] and "<img src=x onerror=1>" in out["text"]
    assert count(page, "script") == 0 and count(page, "img") == 0
    assert not page.errors


def test_links(open_page):
    page = open_blank(open_page)
    run(page, "[x](javascript:alert(1))")
    assert count(page, "a") == 0
    assert page.evaluate("window.__host.textContent") == "[x](javascript:alert(1))"
    run(page, "see [ok](https://example.org) and [here](#ITEM-0001) and a bare https://example.org/x")
    links = page.evaluate("[...window.__host.querySelectorAll('a')].map(a => [a.getAttribute('href'), a.getAttribute('rel'), a.getAttribute('target')])")
    assert links == [["https://example.org", "noopener", "_blank"], ["#ITEM-0001", None, None]]


def test_images_and_unknown_syntax_are_literal(open_page):
    page = open_blank(open_page)
    run(page, "![alt](https://example.org/a.png)\n\n> quote\n\n##### five")
    assert count(page, "img") == 0 and count(page, "a") == 0 and count(page, "blockquote") == 0
    text = page.evaluate("window.__host.textContent")
    assert "![alt](https://example.org/a.png)" in text and "##### five" in text


def test_table_cells_are_labelled_and_numeric_cells_marked(open_page):
    page = open_blank(open_page)
    run(page, "| Phase | Spend | Note |\n|---|---|---|\n| build | $12.89 | sonnet |\n| verify | 1.01M | `x` |")
    assert count(page, "thead th") == 3 and count(page, "tbody tr") == 2
    cells = page.evaluate("[...window.__host.querySelectorAll('tbody td')].map(td => [td.dataset.label, td.className])")
    assert cells[:3] == [["Phase", ""], ["Spend", "num"], ["Note", ""]]
    assert cells[4] == ["Spend", "num"]
    assert "|" not in page.evaluate("window.__host.textContent")


def test_nested_lists_two_deep(open_page):
    page = open_blank(open_page)
    run(page, "- one\n  - inner a\n  - inner b\n- two\n\n1. first\n2. second")
    assert count(page, "ul") == 2 and count(page, "ol") == 1
    assert count(page, "ul > li > ul > li") == 2
    assert page.evaluate("window.__host.querySelector('ul > li').firstChild.textContent") == "one"


def test_fenced_code_keeps_hash_lines(open_page):
    page = open_blank(open_page)
    run(page, "```bash\n# not a heading\n| nor a table |\n```\n\nafter")
    assert count(page, "pre > code[data-lang=bash]") == 1
    assert count(page, "h2") == 0 and count(page, "table") == 0
    assert page.evaluate("window.__host.querySelector('pre code').textContent") == "# not a heading\n| nor a table |"


def test_inline_marks(open_page):
    page = open_blank(open_page)
    run(page, "**bold** and _italic_ and `co_de` and snake_case_name")
    assert count(page, "strong") == 1 and count(page, "em") == 1 and count(page, "code") == 1
    assert "snake_case_name" in page.evaluate("window.__host.textContent")


def test_no_markup_apis_in_sources():
    for rel in ("viz/static/markdown.js", "viz/static/views/work.js"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            assert bad not in text, (rel, bad)
