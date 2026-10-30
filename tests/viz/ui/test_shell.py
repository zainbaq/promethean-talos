"""Shell tests (SPEC-0003): in-place view switching, reduced motion, freshness states, keyboard, markup injection."""
from __future__ import annotations

import subprocess

from .conftest import ROOT


def test_switch_in_place(open_page):
    page = open_page("view=now&data=sample-company")
    page.evaluate("window.__marker = 1")
    page.get_by_role("link", name="Timeline").click()
    page.wait_for_function("location.search.includes('view=timeline')")
    section = page.locator('section[data-view="timeline"]')
    section.wait_for(state="visible")
    assert section.locator("h1").first.text_content() == "Timeline"
    assert page.locator('nav a[aria-current="page"]').inner_text().strip() == "Timeline"
    assert page.evaluate("window.__marker") == 1
    page.go_back()
    page.wait_for_function("location.search.includes('view=now')")
    page.locator('section[data-view="now"]').wait_for(state="visible")
    assert page.evaluate("window.__marker") == 1
    assert page.evaluate("getComputedStyle(document.querySelector('.horizon')).viewTransitionName") == "rings"
    named = page.evaluate("[...document.querySelectorAll('section[data-view=now] *')].filter(e => getComputedStyle(e).viewTransitionName === 'rings').length")
    assert named == 1


def test_reduced_motion(open_page):
    for query, reduced in (("view=now&data=live-active", "reduce"), ("view=now&data=live-active&motion=reduce", None)):
        page = open_page(query, reduced=reduced, wait=".rings .edge-halo")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--dur-2').trim()") == "0ms"
        halo = page.evaluate("(() => { const cs = getComputedStyle(document.querySelector('.rings .edge-halo')); return { name: cs.animationName, opacity: cs.opacity, transform: cs.transform }; })()")
        assert halo["name"] == "none" and halo["opacity"] == "0.2"
        assert halo["transform"].startswith("matrix(1.25, 0, 0, 1.25")


def test_freshness_states(open_page):
    stale = open_page("view=now&data=live-idle&fresh=stale&motion=reduce")
    assert stale.get_attribute(".top__fresh", "data-fresh") == "stale"
    assert "retrying" in stale.inner_text(".top__fresh")
    error = open_page("view=now&data=live-idle&fresh=error&motion=reduce")
    assert error.get_attribute(".top__fresh", "data-fresh") == "error"
    assert error.inner_text(".top__fresh").startswith("record unreadable since")
    assert error.inner_text("#phase") == "Record unreadable"
    assert "is-error" in error.get_attribute(".horizon", "class")
    assert error.locator(".gap-pin").count() == 4
    fresh = open_page("view=now&data=live-idle&motion=reduce")
    assert fresh.get_attribute(".top__fresh", "data-fresh") == "fresh"
    assert fresh.inner_text(".top__fresh") == "fixture live-idle"


def test_keyboard(open_page):
    page = open_page("view=now&data=sample-company&motion=reduce")
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "brand"
    page.keyboard.press("Tab")
    assert "switch" in page.evaluate("document.activeElement.className")
    for name in ("Now", "Timeline", "Work"):
        page.keyboard.press("Tab")
        assert page.evaluate("n => document.activeElement.textContent.trim().startsWith(n)", name)
        assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"
    # Enter on the Timeline link switches the view.
    page.focus('nav a[data-view="timeline"]')
    page.keyboard.press("Enter")
    page.wait_for_function("location.search.includes('view=timeline')")
    page.go_back()
    page.wait_for_function("location.search.includes('view=now')")
    page.focus(".waits li.wait .btn")
    assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"
    page.keyboard.press("Space")
    page.wait_for_function("document.querySelector('.waits .btn').textContent === 'Copied'")
    hrefs = page.locator(".waits a").evaluate_all("els => els.map(a => a.getAttribute('href'))")
    assert hrefs and all(h.startswith("?view=work#ITEM-") for h in hrefs)
    links = page.locator(".rings__centre a, .edge a, section.cycle:not(.summaries) a")
    assert links.count() == 0
    assert page.locator(".summaries a").all_inner_texts() == ["Open Work", "All 68 events"]


def test_no_markup_injection(open_page):
    page = open_page("view=now&data=live-active&motion=reduce")
    payload = "<img src=x onerror=window.__pwned=1>"
    page.evaluate("""(p) => { const next = structuredClone(window.__viz.snapshot); next.events[0].summary = p; next.waiting[0].title = p; window.__viz.push(next); }""", payload)
    page.wait_for_timeout(200)
    assert page.evaluate("window.__pwned") is None
    assert payload in page.locator(".waits li.wait .wait__title").first.inner_text()
    assert payload in page.locator(".summaries").inner_text()
    out = subprocess.run(["grep", "-rnE", r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", "viz/static/"], cwd=ROOT, capture_output=True, text=True)
    assert out.stdout == ""
