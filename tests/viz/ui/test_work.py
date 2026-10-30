"""Work view (SPEC-0005): bands, cards, glyphs, FLIP moves, the markdown report, phone fit, keyboard."""
from __future__ import annotations

import json

import pytest

from .conftest import DESKTOP, PHONE

STATUSES = ["proposed", "ready", "in_progress", "completed", "verified", "blocked"]
BAND = "section[data-key='band:{}']"


def band_ids(page, status):
    return page.evaluate("(s) => [...document.querySelectorAll(`section[data-key='band:${s}'] li.card`)].map(c => c.id)", status)


def open_work(open_page, data="sample-company", **kw):
    return open_page(f"view=work&data={data}&motion=reduce", wait="article.report", **kw)


def with_item(snapshot, item_id, **changes):
    snapshot = json.loads(json.dumps(snapshot))
    for item in snapshot["items"]:
        if item["id"] == item_id:
            item.update(changes)
    return snapshot


def with_report(snapshot, markdown):
    return dict(snapshot, report=dict(snapshot["report"], markdown=markdown, modified_at="2026-10-28T19:00:00Z"))


def test_sample_board(open_page):
    page = open_work(open_page, size=PHONE)
    assert page.locator("li.card").count() == 7
    assert len(band_ids(page, "proposed")) == 5
    assert sorted(band_ids(page, "verified")) == ["ITEM-0001", "ITEM-0002"]
    for status in ("ready", "in_progress", "completed", "blocked"):
        assert "is-empty" in page.get_attribute(BAND.format(status), "class")
    for n, spec, commit in (("1", "SPEC-0001", "4464661"), ("2", "SPEC-0002", "bfaa63b")):
        card = page.locator(f"#ITEM-000{n}")
        assert card.locator(".chip--status").inner_text() == "awaiting release"
        assert f"vc/item-000{n} @ {commit}" in card.locator(".card__meta").inner_text()
        assert card.locator(".owner").inner_text() == "ui-engineer"
        assert card.locator("code", has_text=spec).count() == 1
        for chip in ("P0", "risk normal"):
            assert chip in card.locator(".card__line").inner_text()
    for cid in band_ids(page, "proposed"):
        meta = page.locator(f"#{cid} .card__meta").inner_text()
        assert "no spec" in meta and "no branch" in meta
    assert page.evaluate("[...document.querySelectorAll('li.card')].every(c => c.querySelectorAll('a').length === 1 && c.querySelector('a').getAttribute('href') === '#' + c.id)")
    assert page.locator("svg[width='0']").count() == 1
    assert page.locator("svg[width='0'] symbol[id^='g-']").count() == 6
    assert page.evaluate("[...document.querySelectorAll('svg.glyph')].every(s => s.getAttribute('aria-hidden') === 'true' && s.getAttribute('focusable') === 'false' && s.querySelectorAll('use').length === 1)")
    assert page.evaluate("[...document.querySelectorAll('li.card')].every(c => c.querySelector('use').getAttribute('href') === '#g-' + c.closest('section.band').dataset.key.slice(5))")
    links = page.locator("nav.scale a[href^='#b-']")
    assert links.count() == 6
    assert [links.nth(i).locator(".count").inner_text() for i in range(6)] == ["5", "0", "0", "0", "2", "0"]
    for status in ("ready", "in_progress", "completed", "blocked"):
        assert page.locator(f"nav.scale a[href='#b-{status}'] svg.glyph--empty").count() == 1
        assert page.locator(f"h2#b-{status} svg.glyph--empty").count() == 1
    assert page.locator("nav.scale").is_visible() and page.locator(".card .glyph").first.is_visible()
    assert page.evaluate("getComputedStyle(document.querySelector('nav.scale')).viewTransitionName") == "rings"
    assert page.evaluate("[...document.querySelectorAll('section[data-view=work] *')].filter(e => getComputedStyle(e).viewTransitionName === 'rings').length") == 1
    page.set_viewport_size(DESKTOP)
    assert page.evaluate("getComputedStyle(document.querySelector('nav.scale')).display") == "none"
    assert page.evaluate("[...document.querySelectorAll('.card .glyph')].every(g => getComputedStyle(g).display === 'none')")
    assert not page.errors


def test_all_statuses_land(open_page):
    page = open_work(open_page, "live-active")
    assert page.locator("li.card").count() == 7
    counts = {s: len(band_ids(page, s)) for s in STATUSES}
    assert counts == {"proposed": 0, "ready": 1, "in_progress": 1, "completed": 1, "verified": 2, "blocked": 2}
    heading = lambda s: page.locator(f"h2#b-{s}").inner_text()
    assert "+ shipped" in heading("verified") and "+ assigned" in heading("ready") and "+ rejected" in heading("blocked")
    chips = page.evaluate("[...document.querySelectorAll('.chip--status')].map(c => c.textContent)")
    assert {"shipped", "assigned", "rejected"} <= set(chips)
    assert page.locator("svg.glyph--empty").count() == 2  # only the proposed band: its head and its strip glyph
    assert not page.errors


def test_empty_record(open_page):
    page = open_work(open_page, "empty")
    assert page.locator("li.card").count() == 0
    assert page.locator("nav.scale svg.glyph--empty").count() == 6
    assert "No report yet. The first one is written at cycle close." in page.locator("article.report").inner_text()
    assert page.locator("h2#b-completed").inner_text().endswith("none awaiting verification")


def test_report_rendered(open_page):
    page = open_work(open_page)
    art = page.locator("article.report")
    assert art.locator("h2").first.inner_text() == "Cycle 1 report"
    assert "is-decision" in art.locator("h3", has_text="Needs your decision").get_attribute("class")
    assert art.locator("h3", has_text="Ready to merge (verified by QA)").count() == 1
    assert art.locator("h3", has_text="Budget").count() >= 1
    spend = art.locator("h3", has_text="Spend (measured from transcripts)")
    assert spend.count() == 1 and spend.text_content() == "Spend (measured from transcripts)"
    stray = page.evaluate("""() => { const w = document.createTreeWalker(document.querySelector('article.report'), NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { const t = n.textContent.trim(); if (t.startsWith('#') || t.includes('|')) return t; } return null; }""")
    assert stray is None
    assert "company/reports/cycle-001.md" in art.locator(".report__kicker").inner_text()
    assert art.locator("code", has_text="http://devbox:8000/app/").count() >= 1


def test_card_moves(open_page):
    page = open_work(open_page, size=PHONE)
    page.evaluate("window.__marker = 1")
    page.evaluate("document.querySelector('article.report').scrollIntoView()")
    y = page.evaluate("window.scrollY")
    assert y > 0
    page.evaluate("document.querySelector('#ITEM-0003').dataset.identity = 'same'")
    snap = with_item(page.evaluate("window.__viz.snapshot"), "ITEM-0003", status="in_progress")
    page.evaluate("(s) => window.__viz.push(s)", snap)
    page.wait_for_selector(BAND.format("in_progress") + " #ITEM-0003", timeout=1000)
    li = page.locator(BAND.format("in_progress") + " #ITEM-0003")
    assert li.get_attribute("data-identity") == "same"
    assert "is-empty" not in page.get_attribute(BAND.format("in_progress"), "class")
    page.wait_for_function("document.querySelectorAll('#ITEM-0003 use').length === 1", timeout=1000)
    assert li.locator("use").get_attribute("href") == "#g-in_progress"
    assert page.locator("h2#b-proposed .count").inner_text() == "4"
    assert page.locator("nav.scale a[href='#b-proposed'] .count").inner_text() == "4"
    assert abs(page.evaluate("window.scrollY") - y) <= 2
    assert page.evaluate("window.__marker") == 1


def test_card_moves_animated_stays_within_cap(open_page):
    page = open_page("view=work&data=sample-company", size=PHONE, wait="article.report")
    snap = with_item(page.evaluate("window.__viz.snapshot"), "ITEM-0003", status="in_progress")
    peak = page.evaluate("""(s) => { window.__viz.push(s); return new Set(document.getAnimations().map(a => a.effect && a.effect.target).filter(t => t && t.classList && t.classList.contains('card'))).size; }""", snap)
    assert peak <= 3
    page.wait_for_function("document.querySelectorAll('#ITEM-0003 use').length === 1", timeout=2000)


def test_updates_added_removed_changed(open_page):
    page = open_work(open_page, size=PHONE)
    snap = page.evaluate("window.__viz.snapshot")
    extra = dict(snap["items"][2], id="ITEM-0099", title="New one", status="blocked")
    page.evaluate("(s) => window.__viz.push(s)", dict(snap, items=snap["items"] + [extra]))
    page.wait_for_selector(BAND.format("blocked") + " #ITEM-0099")
    assert page.locator("li.card").count() == 8
    page.evaluate("(s) => window.__viz.push(s)", dict(snap, items=[i for i in snap["items"] if i["id"] != "ITEM-0007"]))
    page.wait_for_function("document.querySelectorAll('li.card').length === 7 - 1", timeout=2000)
    page.evaluate("(s) => window.__viz.push(s)", with_item(snap, "ITEM-0004", title="Renamed", priority="P0", risk="high"))
    assert page.locator("#ITEM-0004 .card__title a").inner_text() == "Renamed"
    assert page.locator("#ITEM-0004 .chip--p0").count() == 1 and page.locator("#ITEM-0004 .chip--risk-high").count() == 1


BUDGET = "\n\n## Budget and spend\n\n| Phase | Elapsed | Tokens | Note |\n|---|---|---|---|\n| build | 0h04m | 1.01M | sonnet 74%, fable 26%; 2 ui-engineer runs 45.8k + 42.7k |\n| verify | ~8 min | see spend | reviews 36k+37k, test-engineer 24k |\n| cycle | 0h37m | 5.01M | 138 model calls; fable 56% |\n"


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("data", ["sample-company", "live-active"])
def test_phone_fit(open_page, scheme, data):
    page = open_work(open_page, data, size=PHONE, scheme=scheme)
    snap = page.evaluate("window.__viz.snapshot")
    page.evaluate("(s) => window.__viz.push(s)", with_report(snap, snap["report"]["markdown"] + BUDGET))
    page.wait_for_selector("article.report table")
    sw = page.evaluate("[document.documentElement.scrollWidth, innerWidth, document.querySelector('article.report').scrollWidth, document.querySelector('article.report').clientWidth]")
    assert sw[0] <= sw[1] and sw[2] <= sw[3], sw
    assert page.locator(".report__inner").count() == 1
    assert page.locator("article.report tbody tr").count() == 3
    assert page.evaluate("[...document.querySelectorAll('article.report td')].every(td => td.dataset.label && getComputedStyle(td, '::before').content.length > 2)")


def test_keyboard(open_page):
    page = open_work(open_page, size=PHONE)
    snap = page.evaluate("window.__viz.snapshot")
    page.evaluate("(s) => window.__viz.push(s)", with_report(snap, snap["report"]["markdown"] + "\n\nSee [docs](https://example.org/docs)."))
    page.wait_for_selector("article.report a")
    seen = {}
    for _ in range(80):
        page.keyboard.press("Tab")
        info = page.evaluate("""() => { const a = document.activeElement; const cs = getComputedStyle(a); return { href: a.getAttribute('href'), card: !!a.closest('li.card'), report: !!a.closest('article.report'), outline: cs.outlineStyle, width: cs.outlineWidth }; }""")
        if info["card"] and "card" not in seen:
            seen["card"] = info
            page.keyboard.press("Enter")
            assert page.evaluate("location.hash") == info["href"]
        if info["report"]:
            seen["report"] = info
            break
    assert set(seen) == {"card", "report"}
    for info in seen.values():
        assert info["outline"] != "none" and info["width"] != "0px"
