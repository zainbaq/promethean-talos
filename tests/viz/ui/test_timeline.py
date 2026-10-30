"""Timeline view tests (SPEC-0004): counts, order and groups, filters, live insert, run re-key, keyboard, long record, phone fit.

Fixture states only (`?data=`); the live-server acceptance lines are for the integration checkout.
"""
from __future__ import annotations

import copy
import json
import time

import pytest

from .conftest import DESKTOP, PHONE, ROOT

SAMPLE = "view=timeline&data=sample-company&open=all&motion=reduce"
DEFAULT = "view=timeline&data=sample-company&motion=reduce"
EMPTY = "view=timeline&data=empty&motion=reduce"
READY = "li.event"
FIRST_RUN = "EVT-20261028180433-d87e"
PROBE = "EVT-20261029000000-t001"


def fixture(name="sample-company"):
    return json.loads((ROOT / "viz" / "static" / "fixtures" / f"{name}.json").read_text(encoding="utf8"))


@pytest.fixture
def sample(open_page):
    return open_page(SAMPLE, wait=READY)


def count_line(page):
    return " ".join(page.locator(".filters__count > span").first.inner_text().split())


def visible_ids(page):
    return page.locator("li.event:not([hidden])").evaluate_all("els => els.map(e => e.id)")


def probe_snapshot(snap, run=None, phase=None, cycle=1):
    out = copy.deepcopy(snap)
    ev = {"id": PROBE, "ts": "2026-10-29T00:00:00Z", "actor": "coordinator", "tier": "execution", "event": "note", "ref": None,
          "summary": "freshness probe", "evidence": [], "branch": None, "cycle": cycle, "phase": phase, "run": run, "extra": {}}
    out["events"].insert(0, ev)
    out["counts"]["events"] += 1
    out["version"] = out.get("version", 0) + 1
    return out


def test_fixture_counts(sample):
    page = sample
    assert page.locator("li.event").count() == 68
    assert page.locator("li.event > span.tick[aria-hidden='true']").count() == 68
    assert page.locator("select[name=type] option").count() == 25
    assert page.locator("select[name=actor] option").count() == 10
    assert count_line(page) == "68 of 68 events · 2 cycles · 9 runs"
    assert page.locator(".rings__count").inner_text().replace("\n", "") == "68events · 2 cycles · 9 runs"
    assert page.locator(".rings__count small").inner_text() == "events · 2 cycles · 9 runs"
    svg = page.locator("svg.rings")
    assert svg.get_attribute("aria-hidden") == "true"
    assert svg.locator(".arc[data-run]").count() == 9
    labels = svg.locator("text.label--phase textPath").all_text_contents()
    assert labels == ["kickoff", "plan", "cycle-build", "cycle-verify", "cycle-close", "retro", "cycle-close"]
    assert svg.locator(".tick[data-event]").count() == 68
    assert svg.locator(".gap-pin").count() == 2
    assert page.locator("details.group").count() == 9
    assert page.locator("details.group[open]").count() == 9
    assert "Growth rings map: 2 cycles, 9 runs, 68 events" in page.locator(".stage .sr-only").inner_text()
    assert page.evaluate("getComputedStyle(document.querySelector('.stage')).viewTransitionName") == "rings"
    assert page.evaluate("[...document.querySelectorAll('section[data-view=timeline] *')].filter(e => getComputedStyle(e).viewTransitionName === 'rings').length") == 1
    assert page.errors == []


def test_default_open_state(open_page):
    page = open_page(DEFAULT, wait=READY)
    states = page.locator("details.group").evaluate_all("els => els.map(e => [e.closest('section').getAttribute('data-key'), e.open])")
    assert [s for s in states if s[0] == "cycle:1"] == [["cycle:1", True]] * 5
    assert [s for s in states if s[0] == "cycle:0"] == [["cycle:0", False]] * 4
    hint = page.locator("section[data-key='cycle:0'] details.group").first.locator(".group__hint")
    assert hint.count() == 1 and " · " in hint.inner_text()
    assert page.locator("section[data-key='cycle:1'] .group__hint").count() == 0
    assert page.locator("svg.rings .arc-hi.is-open").count() == 5
    assert page.errors == []


def test_order_and_groups(sample):
    page = sample
    sections = page.locator(".ledger > section")
    assert sections.count() == 2
    assert sections.nth(0).locator("h2").inner_text().startswith("Cycle 1")
    assert sections.nth(1).locator("h2").inner_text().startswith("Cycle 0 (planning)")
    assert "38 events · 17:24:28 to 18:04:33 · ended, 0h37m" in sections.nth(0).locator("h2").inner_text()

    def summaries(section):
        return section.locator("details.group").evaluate_all(
            "els => els.map(e => [e.querySelector('.group__phase').textContent, e.querySelector('.group__count').textContent])")

    assert summaries(sections.nth(0)) == [["cycle-close", "4"], ["retro", "7"], ["cycle-close", "8"], ["cycle-verify", "10"], ["cycle-build", "9"]]
    assert summaries(sections.nth(1)) == [["review", "3"], ["plan", "17"], ["review", "3"], ["kickoff", "7"]]
    first = page.locator("li.event").evaluate_all("els => els.slice(0, 5).map(e => [e.querySelector('time').textContent, e.querySelector('.event__type').textContent])")
    assert first == [["18:04:33", "run.completed"], ["18:04:18", "note"], ["18:04:18", "note"], ["18:02:04", "cycle.ended"], ["17:59:39", "run.completed"]]

    snap = fixture()
    by_id = {e["id"]: e for e in snap["events"]}
    for li in page.locator("li.event").element_handles():
        ev = by_id[li.get_attribute("id")]
        assert li.query_selector(".event__actor").inner_text() == ev["actor"]
        assert li.query_selector(".event__type").inner_text() == ev["event"]
        assert li.query_selector(".event__summary").inner_text() == ev["summary"]
        refs = li.query_selector_all(".event__refs a, .event__refs code")
        assert len(refs) == len(ev["evidence"])
        for node, ref in zip(refs, ev["evidence"]):
            if ref.startswith("EVT-"):
                assert node.evaluate("e => e.tagName") == "A" and node.get_attribute("href") == f"#{ref}"
            else:
                assert node.evaluate("e => e.tagName") == "CODE"
    assert page.locator("a[href='#']").count() == 0
    assert page.locator(".event__refs").count() > 0


def test_filters(sample):
    page = sample
    page.locator("select[name=actor]").select_option("ceo")
    ids = visible_ids(page)
    assert len(ids) == 4
    assert count_line(page).startswith("4 of 68 events")
    assert "actor=ceo" in page.evaluate("location.search")
    assert page.locator("section[data-key='cycle:1'] details.group.is-filtered-out").count() == 5
    h2 = page.locator("h2#c1")
    assert "is-filtered-out" in h2.get_attribute("class")
    assert h2.locator(".cycle-h__meta").inner_text().startswith("0 of 38 events match")
    assert "is-filtered" in page.locator("svg.rings").get_attribute("class")
    match = page.locator("svg.rings .tick.is-match").evaluate_all("els => els.map(e => e.dataset.event)")
    assert sorted(match) == sorted(ids) and len(match) == 4
    opacity = lambda sel: page.locator(sel).first.evaluate("e => getComputedStyle(e).opacity")  # noqa: E731
    assert opacity("svg.rings .tick.is-match") == "1"
    assert opacity("svg.rings .tick:not(.is-match)") == "0.12"
    assert opacity("svg.rings .arc") == "0.5"
    assert page.locator(".rings__count > span").inner_text() == "4"
    assert page.locator(".rings__count small").inner_text() == "of 68 events · actor ceo"
    assert page.locator(".filters__count code").inner_text() == "ceo"
    assert "is-set" in page.locator("select[name=actor]").get_attribute("class")

    page.locator("select[name=actor]").select_option("")
    page.locator("select[name=type]").select_option("run.completed")
    assert len(visible_ids(page)) == 9
    assert page.locator("svg.rings .tick.is-match").count() == 9
    assert "type=run.completed" in page.evaluate("location.search") and "actor" not in page.evaluate("location.search")

    page.locator("button.link-btn").click()
    assert len(visible_ids(page)) == 68
    assert count_line(page) == "68 of 68 events · 2 cycles · 9 runs"
    assert "is-filtered" not in page.locator("svg.rings").get_attribute("class")
    assert page.locator("button.link-btn").is_disabled()
    assert page.locator("details.group.is-filtered-out").count() == 0
    assert page.locator("details.group[open]").count() == 9

    # each filter responds within 200 ms: option change to visible-count change, measured in the page
    ms = page.evaluate("""() => {
      const sel = document.querySelector('select[name=actor]');
      const t = performance.now();
      sel.value = 'ceo';
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      const n = document.querySelectorAll('li.event:not([hidden])').length;
      return [performance.now() - t, n];
    }""")
    assert ms[1] == 4 and ms[0] < 200
    assert page.errors == []


def test_filter_from_url(open_page):
    page = open_page("view=timeline&data=sample-company&actor=ceo&open=all&motion=reduce", wait=".cycle-h")
    assert len(visible_ids(page)) == 4
    assert page.locator("select[name=actor]").input_value() == "ceo"
    assert page.locator("svg.rings .tick.is-match").count() == 4


def test_live_insert(sample):
    page = sample
    snap = page.evaluate("window.__viz.snapshot")
    page.evaluate("window.scrollTo(0, 1000)")
    page.evaluate("window.__marker = 1")
    y0 = page.evaluate("window.scrollY")
    assert y0 > 900
    tops = page.locator("li.event").evaluate_all("els => Object.fromEntries(els.map(e => [e.id, e.getBoundingClientRect().top]))")
    animating = page.evaluate("""(next) => {
      window.__viz.push(next);
      return document.getAnimations().map(a => a.effect && a.effect.target).filter(Boolean)
        .reduce((n, t) => { if (t.classList.contains('event')) n.event++; if (t.classList.contains('tick')) n.tick++; return n; }, { event: 0, tick: 0 });
    }""", probe_snapshot(snap))
    assert animating["event"] <= 8 and animating["tick"] <= 8
    row = page.locator(f"li.event[id='{PROBE}']")
    assert row.count() == 1
    assert row.evaluate("e => e.closest('details.group').dataset.key") == "current:1"
    assert page.locator(".ledger > section").first.locator("li.event").first.get_attribute("id") == PROBE
    assert page.locator("svg.rings g.ring[data-cycle='1'] .tick[data-event='%s']" % PROBE).count() == 1
    assert page.locator("svg.rings .tick[data-event]").count() == 69
    # SPEC-0004 asks for "scrollY unchanged within 2 px" AND every row's top unchanged within 2 px; with a node inserted above the
    # viewport these cannot both hold. Motion 2 (insertKeepingScroll) keeps what the reader sees: scrollY moves by the inserted height.
    inserted = page.evaluate(f"document.getElementById('{PROBE}').closest('details.group').getBoundingClientRect().height")
    assert abs((page.evaluate("window.scrollY") - y0) - inserted) <= 2
    assert page.evaluate("window.__marker") == 1
    after = page.locator("li.event").evaluate_all("els => Object.fromEntries(els.map(e => [e.id, e.getBoundingClientRect().top]))")
    for rid, top in tops.items():
        assert abs(after[rid] - top) < 2, rid
    assert count_line(page) == "69 of 69 events · 2 cycles · 9 runs"
    assert page.errors == []


def binned_snapshot(snap):
    """401 events in one run of cycle 1 (oldest 200 type a, then 200 type b, then the run.completed), so the ring bins them."""
    out = copy.deepcopy(snap)
    base = next(e for e in snap["events"] if e["cycle"] == 1)
    keep = [e for e in snap["events"] if e["cycle"] == 0]
    run = "EVT-20261029000000-run1"
    events = []
    for i in range(400):
        ev = copy.deepcopy(base)
        ev.update(id=f"EVT-20261029000000-{i:04d}", ts=f"2026-10-29T0{i // 3600}:{(i // 60) % 60:02d}:{i % 60:02d}Z", event="a" if i < 200 else "b",
                  actor="coordinator", tier="execution", ref=None, summary=f"probe {i}", evidence=[], cycle=1, phase="plan", run=run, extra={})
        events.append(ev)
    done = copy.deepcopy(base)
    done.update(id=run, ts="2026-10-29T01:00:00Z", event="run.completed", actor="talos-run", tier="mechanical", ref="plan", summary="plan: success",
                evidence=[], cycle=1, phase="plan", run=run, extra={"phase": "plan", "cost_usd": 1.0})
    events.append(done)
    events.reverse()
    out["events"] = events + keep
    out["counts"]["events"] = len(out["events"])
    out["event_types"] = sorted({e["event"] for e in out["events"]})
    out["actors"] = sorted({e["actor"] for e in out["events"]})
    out["version"] = out.get("version", 0) + 1
    return out


def test_binned_ticks_match(sample):
    page = sample
    page.evaluate("(s) => window.__viz.push(s)", binned_snapshot(page.evaluate("window.__viz.snapshot")))
    ring = page.locator("svg.rings g.ring[data-cycle='1']")
    ticks = ring.locator(".tick[data-event]").evaluate_all("els => els.map(e => [e.dataset.event, Number(e.dataset.count || 1)])")
    assert 1 < len(ticks) <= 360 and sum(n for _, n in ticks) == 401
    # the contract: a bin's data-event is its oldest member, members are the next data-count events of the run, oldest first
    assert ticks[0][0] == "EVT-20261029000000-0000"
    page.locator("select[name=type]").select_option("a")
    assert len(visible_ids(page)) == 200
    expected, start = set(), 0
    for tid, n in ticks:
        if start < 200:
            expected.add(tid)
        start += n
    match = set(ring.locator(".tick.is-match").evaluate_all("els => els.map(e => e.dataset.event)"))
    assert match == expected and 0 < len(match) < len(ticks)
    assert page.errors == []


def test_removed_events_leave(sample):
    page = sample
    snap = page.evaluate("window.__viz.snapshot")
    snap["events"] = snap["events"][1:]
    snap["counts"]["events"] -= 1
    snap["version"] += 1
    page.evaluate("(s) => window.__viz.push(s)", snap)
    assert page.locator("li.event").count() == 67
    assert count_line(page).startswith("67 of 67 events")


def test_run_rekeys_current_group(sample):
    page = sample
    snap = page.evaluate("window.__viz.snapshot")
    page.evaluate("(s) => window.__viz.push(s)", probe_snapshot(snap))
    page.evaluate(f"document.getElementById('{PROBE}').__mark = 'same-node'")
    second = probe_snapshot(snap, run="EVT-r1", phase="cycle-build")
    second["events"].insert(0, {"id": "EVT-r1", "ts": "2026-10-29T00:00:05Z", "actor": "talos-run", "tier": "mechanical", "event": "run.completed",
                                "ref": "cycle-build", "summary": "cycle-build on sonnet: success", "evidence": [], "branch": None, "cycle": 1,
                                "phase": "cycle-build", "run": "EVT-r1", "extra": {"phase": "cycle-build", "cost_usd": 0.5}})
    second["counts"]["events"] += 1
    second["version"] += 1
    page.evaluate("(s) => window.__viz.push(s)", second)
    info = page.evaluate(f"""() => {{
      const li = document.getElementById('{PROBE}');
      const g = li.closest('details.group');
      return [li.__mark, g.dataset.key, g.querySelector('.group__phase').textContent, g.querySelectorAll('li.event').length];
    }}""")
    assert info == ["same-node", "EVT-r1", "cycle-build", 2]
    assert page.locator("details.group[data-key^='current:']").count() == 0
    assert page.locator("svg.rings .arc[data-run='EVT-r1']").count() == 1
    assert page.errors == []


def test_keyboard_and_collapse(sample):
    page = sample
    for _ in range(30):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.tagName") == "SUMMARY":
            break
    assert page.evaluate("document.activeElement.tagName") == "SUMMARY"
    assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"
    group = page.locator("details.group").first
    hi = page.locator(f".arc-hi[data-run='{FIRST_RUN}']")
    assert group.get_attribute("data-key") == FIRST_RUN
    assert "is-open" in hi.get_attribute("class")
    page.keyboard.press("Space")
    assert group.evaluate("e => e.open") is False
    page.wait_for_function("document.querySelector('details.group').querySelector('.group__hint')")
    assert " · " in group.locator(".group__hint").inner_text() or group.locator(".group__hint").inner_text()
    assert "run.completed" in group.locator(".group__hint").inner_text()
    assert "is-open" not in hi.get_attribute("class")
    page.keyboard.press("Enter")
    assert group.evaluate("e => e.open") is True
    page.wait_for_function("!document.querySelector('details.group').querySelector('.group__hint')")
    assert "is-open" in hi.get_attribute("class")
    page.wait_for_function("document.querySelectorAll('li.event[data-stagger]').length === 0")
    assert page.locator(".ledger[data-filtering]").count() == 0


def test_evt_anchor_opens_closed_group(open_page):
    page = open_page(DEFAULT, wait=READY)
    # an EVT link inside the open cycle pointing into the closed cycle 0, if the record has one; otherwise build the case
    snap = page.evaluate("window.__viz.snapshot")
    target = next(e for e in reversed(snap["events"]) if e["cycle"] == 0)
    page.evaluate("""(id) => {
      const a = document.createElement('a'); a.href = '#' + id; a.id = 'probe-link'; a.textContent = 'x';
      document.querySelector('.event__summary').append(a);
    }""", target["id"])
    group = page.locator(f"li[id='{target['id']}']").locator("xpath=ancestor::details[1]")
    assert group.evaluate("e => e.open") is False
    page.locator("#probe-link").click()
    assert group.evaluate("e => e.open") is True


def test_empty(open_page):
    page = open_page(EMPTY, wait=".cycle-h")
    assert count_line(page) == "0 of 0 events · 1 cycle · 0 runs"
    assert page.locator(".cycle-h").count() == 1
    assert page.locator("h2#c0").inner_text().startswith("Cycle 0 (planning)")
    assert "0 events" in page.locator("h2#c0 .cycle-h__meta").inner_text()
    svg = page.locator("svg.rings")
    assert svg.locator(".track").count() == 1 and svg.locator(".arc").count() == 0 and svg.locator(".tick").count() == 0
    assert page.locator(".rings__count").inner_text().replace("\n", "") == "0events · 1 cycle · 0 runs"
    assert page.errors == []


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("query", [SAMPLE, DEFAULT])
def test_phone_fit(open_page, scheme, query):
    page = open_page(query, size=PHONE, scheme=scheme, wait=READY)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # every summary is fully visible in open groups
    clipped = page.evaluate("""() => [...document.querySelectorAll('details[open] .event__summary')]
      .filter(e => e.scrollWidth > e.clientWidth + 1 || getComputedStyle(e).textOverflow === 'ellipsis').length""")
    assert clipped == 0
    assert page.errors == []


def test_desktop_layout(open_page):
    page = open_page(SAMPLE, size=DESKTOP, wait=READY)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    rings = page.locator("svg.rings").bounding_box()
    panel = page.locator(".ledger").bounding_box()
    assert rings["x"] + rings["width"] <= panel["x"] + 1


def big_snapshot():
    snap = fixture()
    cycle0 = [e for e in snap["events"] if e["cycle"] == 0]
    cycle1 = [e for e in snap["events"] if e["cycle"] == 1][:34]
    events = []
    for c in range(8, 0, -1):
        for e in cycle1:
            n = copy.deepcopy(e)
            n["id"] = f"{e['id']}-c{c}"
            n["run"] = f"{e['run']}-c{c}" if e.get("run") else None
            n["cycle"] = c
            events.append(n)
    events.extend(cycle0)
    snap["events"] = events
    snap["counts"]["events"] = len(events)
    snap["cycle"]["number"] = 8
    return snap


def test_long_record(browser, static_url):
    big = big_snapshot()
    assert 290 <= len(big["events"]) <= 310
    context = browser.new_context(viewport=PHONE, color_scheme="light")
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script("""window.__long = [];
          new PerformanceObserver(l => { for (const e of l.getEntries()) window.__long.push(e.duration); }).observe({ entryTypes: ['longtask'] });""")
        page.route("**/static/fixtures/sample-company.json", lambda route: route.fulfill(json=big))
        cdp = context.new_cdp_session(page)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        t0 = time.perf_counter()
        page.goto(f"{static_url}/?view=timeline&data=sample-company")
        page.wait_for_selector("li.event")
        page.wait_for_function("document.querySelectorAll('li.event').length === %d" % len(big["events"]))
        assert time.perf_counter() - t0 < 2.0
        svg = page.locator("svg.rings")
        assert svg.locator("g.ring").count() == 9
        assert svg.locator("g.ring.ring--full").count() == 4 and svg.locator("g.ring.ring--thin").count() == 5
        assert svg.locator("g.ring.ring--recent").count() == 2
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        # a push of one more event: no long task over 200 ms
        page.evaluate("window.__long.length = 0")
        page.evaluate("(s) => window.__viz.push(s)", probe_snapshot(big, cycle=8))
        page.wait_for_selector(f"li.event[id='{PROBE}']")
        page.wait_for_timeout(300)
        assert [d for d in page.evaluate("window.__long") if d > 200] == []
        # collapse and expand by keyboard
        page.locator("summary").first.focus()
        page.keyboard.press("Space")
        assert page.locator("details.group").first.evaluate("e => e.open") is False
        page.keyboard.press("Enter")
        assert page.locator("details.group").first.evaluate("e => e.open") is True
        context.set_default_timeout(5000)
        page.emulate_media(color_scheme="dark")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert errors == []
    finally:
        context.close()


def test_old_rings_have_no_tick_transition(browser, static_url):
    big = big_snapshot()
    context = browser.new_context(viewport=PHONE, color_scheme="light")
    try:
        page = context.new_page()
        page.route("**/static/fixtures/sample-company.json", lambda route: route.fulfill(json=big))
        page.goto(f"{static_url}/?view=timeline&data=sample-company")
        page.wait_for_selector("li.event")
        old = page.locator("g.ring[data-cycle='3'] .tick").first.evaluate("e => getComputedStyle(e).transitionDuration")
        new = page.locator("g.ring[data-cycle='8'] .tick").first.evaluate("e => getComputedStyle(e).transitionDuration")
        assert old == "0s" and new != "0s"
    finally:
        context.close()


### ---- ITEM-0018 (SPEC-0011): the disc stays inside its column at every desktop width and centred everywhere ----
def map_boxes(page):
    return page.evaluate("""(sels) => Object.fromEntries(sels.map(s => { const r = document.querySelector(s).getBoundingClientRect();
      return [s, { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width, height: r.height }]; }))""",
                         ["svg.rings", ".stage", ".picture--map", "form.filters", ".ledger"])


def disjoint(a, b):
    return a["right"] <= b["x"] or b["right"] <= a["x"] or a["bottom"] <= b["y"] or b["bottom"] <= a["y"]


@pytest.mark.parametrize("width", [900, 1000, 1100])
def test_disc_inside_its_column(open_page, width):
    page = open_page(DEFAULT, size={"width": width, "height": 900}, wait=READY)
    b = map_boxes(page)
    rings, picture = b["svg.rings"], b[".picture--map"]
    assert rings["x"] >= picture["x"] - 1 and rings["right"] <= picture["right"] + 1
    assert disjoint(rings, b["form.filters"]) and disjoint(rings, b[".ledger"])
    assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")
    assert page.errors == []


@pytest.mark.parametrize("size", [(390, 844), (800, 900), (1280, 800)])
def test_disc_centred_in_its_stage(open_page, size):
    page = open_page(DEFAULT, size={"width": size[0], "height": size[1]}, wait=READY)
    b = map_boxes(page)
    rings, stage = b["svg.rings"], b[".stage"]
    assert abs((rings["x"] + rings["width"] / 2) - (stage["x"] + stage["width"] / 2)) <= 1
    if size[0] == 1280:
        assert rings["width"] == 460  # --rings-desktop: clamp(420px, 100vh - 340px, 620px) at 800 px tall
    assert page.evaluate("document.documentElement.scrollWidth === window.innerWidth")
    assert page.errors == []


### ---- ITEM-0019 (SPEC-0012): the pin labels clear the header rule at every desktop width; the centre stays on the disc ----
@pytest.mark.parametrize("width", [900, 1000, 1100, 1280])
def test_pin_labels_clear_the_header(open_page, width):
    page = open_page(DEFAULT, size={"width": width, "height": 900}, wait=READY)
    m = page.evaluate("""() => { const box = s => document.querySelector(s).getBoundingClientRect();
      const rule = box('.top').bottom, svg = box('svg.rings'), c = box('.rings__centre');
      return { rule, tops: [...document.querySelectorAll('svg.rings .pin text.label')].map(t => t.getBoundingClientRect().top),
        dx: (c.x + c.width / 2) - (svg.x + svg.width / 2), dy: (c.y + c.height / 2) - (svg.y + svg.height / 2) }; }""")
    assert m["rule"] == 60 and len(m["tops"]) == 2  # desktop header; the sample record has two pins (ITEM-0001, ITEM-0002)
    assert min(m["tops"]) >= m["rule"] + 8  # the topmost label clears the header rule by --space-2
    assert abs(m["dx"]) <= 1 and abs(m["dy"]) <= 1
    assert page.errors == []
