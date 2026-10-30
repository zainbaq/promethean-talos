"""Now view tests (SPEC-0003): fixture states by URL, ring geometry, motion contracts, phone fit."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from .conftest import DESKTOP, PHONE, ROOT

SAMPLE = "view=now&data=sample-company&motion=reduce"
ACTIVE = "view=now&data=live-active&motion=reduce"
IDLE = "view=now&data=live-idle&motion=reduce"
EMPTY = "view=now&data=empty&motion=reduce"


def text(page, selector):
    return page.locator(selector).first.inner_text().strip()


def fixture(name):
    return json.loads((ROOT / "viz" / "static" / "fixtures" / f"{name}.json").read_text(encoding="utf8"))


def test_sample_counts(page):
    assert text(page, "#phase") == "Idle"
    assert text(page, ".phase__meta") == "cycle 1 · closed\nlast: cycle-close 18:04"
    assert text(page, ".edge .count") == "unavailable"
    assert "Activity unavailable." in text(page, ".edge__note")
    titles = page.locator(".waits li.wait .wait__title").all_inner_texts()
    assert len(titles) == 2
    assert titles[0].startswith("ITEM-0001") and titles[1].startswith("ITEM-0002")
    assert text(page, ".nav__count") == "2"
    assert "7 items: 2 verified, 5 proposed" in text(page, ".summaries .summary-line")
    assert text(page, ".cycle .count") == "closed"
    figures = page.locator(".figures > div")
    assert figures.nth(1).locator(".num").inner_text() == "$12.89"
    assert figures.nth(2).locator(".num").inner_text() == "0.54M"
    assert figures.nth(2).locator(".sub").inner_text() == "runs only, no transcripts"
    assert page.errors == []


def test_ring_sample(page):
    snap = fixture("sample-company")
    ids = {e["id"] for e in snap["events"]}
    svg = page.locator("svg.rings")
    assert svg.get_attribute("aria-hidden") == "true"
    rings = svg.locator("g.ring")
    assert rings.count() == 2
    assert [rings.nth(i).get_attribute("data-cycle") for i in range(2)] == ["0", "1"]
    assert all("ring--full" in (rings.nth(i).get_attribute("class") or "") for i in range(2))
    assert "ring--recent" in rings.nth(1).get_attribute("class")
    assert svg.locator(".track").count() == 2
    runs = svg.locator(".arc").evaluate_all("els => els.map(e => e.dataset.run)")
    assert len(runs) == 9 and len(set(runs)) == 9
    assert svg.locator(".arc--live").count() == 0
    tick_ids = svg.locator(".tick").evaluate_all("els => els.map(e => e.dataset.event)")
    assert len(tick_ids) == 68 and set(tick_ids) <= ids
    assert svg.locator(".tick--ceo").count() == 4
    assert svg.locator(".label--cycle").all_text_contents() == ["cycle 0", "cycle 1"]
    assert svg.locator(".gap-cap").count() == 2
    pins = svg.locator(".gap-pin").evaluate_all("els => els.map(e => e.dataset.key)")
    assert pins == ["gate:release:ITEM-0001", "gate:release:ITEM-0002"]
    assert svg.locator(".label--attention").all_text_contents() == ["ITEM-0001", "ITEM-0002"]
    assert svg.locator("g.edge").count() == 0
    assert page.locator(".sr-only").first.text_content() == "Growth rings: 2 cycles, 68 events; 2 gaps waiting on you."


def test_active_and_idle(open_page):
    page = open_page(ACTIVE)
    assert " ".join(text(page, "#phase").split()) == "Running build"
    assert page.locator("h1#phase code").get_attribute("data-phase") == "cycle-build"
    assert "is-live" in page.locator(".horizon").get_attribute("class")
    assert text(page, ".phase__meta") == "running · 0h29m\ncycle 1 · open"
    assert text(page, ".edge .count") == "2"
    agents = page.locator("li.agent")
    assert agents.count() == 3
    first, second, third = (agents.nth(i).inner_text() for i in range(3))
    assert "main session" in first and "on cycle-build" in first and "05:59:52 · 8 s ago" in first
    assert "engineer" in second and "on ITEM-0003" in second and "05:59:18 · 42 s ago" in second
    assert "agent--recent" in agents.nth(2).get_attribute("class")
    assert "chief-architect" in third and "was on SPEC-0003" in third and "05:55:45 · 4 min 15 s ago" in third
    cards = page.locator(".waits li.wait")
    assert cards.count() == 4
    for i in range(4):
        assert cards.nth(i).locator(".cmd code").inner_text().startswith("tools/talos/run review")
    assert cards.nth(0).locator(".wait__body strong").inner_text().startswith("Proposed default:")
    svg = page.locator("svg.rings")
    assert svg.locator(".arc--live").count() == 1
    assert abs(float(svg.locator(".arc--live").get_attribute("data-deg")) - 28.9) <= 0.2
    open_ring = svg.locator('g.ring--open[data-cycle="1"]')
    assert open_ring.get_attribute("data-fill") == "0.87"
    assert open_ring.locator(".label--cycle").text_content() == "cycle 1 open"
    assert svg.locator(".gap-pin").count() == 4
    assert svg.locator(".label--attention").all_text_contents() == ["Q-0001", "Q-0002", "charter", "ITEM-0001"]
    assert svg.locator(".edge-halo").count() == 1 and svg.locator(".edge-tip").count() == 1
    assert svg.locator(".edge-dot").count() == 3 and svg.locator(".edge-dot--recent").count() == 1
    assert text(page, ".cycle .figures > div:nth-child(3) .sub") == "53 model calls, transcripts"

    idle = open_page(IDLE)
    assert text(idle, "#phase") == "Idle"
    assert text(idle, ".phase__meta") == "cycle 1 · open\nlast: cycle-close 18:04"
    assert idle.locator(".arc--live").count() == 0 and idle.locator("g.edge").count() == 0
    assert idle.locator("li.agent.agent--recent").count() == 1
    assert text(idle, ".edge__note").startswith("Nobody active. Last run cycle-close on sonnet finished 18:04:33, 7 turns, $1.08.")


def test_waiting_questions_and_gate(open_page):
    page = open_page(ACTIVE)
    cards = page.locator(".waits li.wait")
    assert "Q-0001" in cards.nth(0).locator(".wait__kind").inner_text()
    assert "Q-0002" in cards.nth(1).locator(".wait__kind").inner_text()
    assert cards.nth(2).locator(".wait__kind").inner_text().lower().startswith("charter gate")
    assert cards.nth(2).locator(".wait__meta").inner_text() == "EVT-20261028042946-12f2 · no charter.approved event"
    assert "Proposed default" in cards.nth(1).locator(".wait__body").inner_text()
    assert cards.nth(3).locator(".wait__title a").get_attribute("href") == "?view=work#ITEM-0001"


def test_empty_record(open_page):
    page = open_page(EMPTY)
    assert text(page, ".phase__meta") == "planning\nno events yet"
    assert page.locator(".rings .track").count() == 1 and page.locator(".rings .arc").count() == 0 and page.locator(".rings .tick").count() == 0
    assert text(page, ".summaries .summary-line") == "No items yet."
    assert "Nothing is waiting on you. The ring is sealed." in text(page, ".waiting")
    assert page.locator(".nav__count").is_hidden()
    assert text(page, ".figures > div:nth-child(2) .num") == "$0.00"


def test_activity_unavailable_keeps_blocks(open_page):
    page = open_page(SAMPLE)
    assert text(page, ".edge .count") == "unavailable"
    assert page.locator(".cycle .figures").is_visible() and page.locator(".waiting .waits").is_visible() and page.locator("svg.rings").is_visible()


def push_js(mutation):
    return f"""() => {{ const next = structuredClone(window.__viz.snapshot); {mutation}; window.__viz.push(next); }}"""


def test_ring_binning(open_page):
    page = open_page(ACTIVE)
    page.evaluate(push_js("""
      const run = next.events.find(e => e.cycle === 1 && e.run).run;
      const extra = [];
      for (let i = 0; i < 400; i++) extra.push({ id: `EVT-20261029060000-n${i}`, ts: next.generated_at, actor: "engineer", tier: "execution", event: "note", ref: null, summary: "n", evidence: [], branch: null, cycle: 1, phase: null, run, extra: {} });
      next.events = extra.concat(next.events); next.counts.events += 400;
    """))
    page.wait_for_timeout(100)
    info = page.evaluate("""() => { const ticks = [...document.querySelectorAll('g.ring[data-cycle="1"] .tick')];
      return { n: ticks.length, sum: ticks.reduce((s, t) => s + Number(t.dataset.count || 1), 0), binned: ticks.some(t => Number(t.dataset.count) > 1) }; }""")
    assert info["n"] <= 360 and info["binned"]
    assert info["sum"] == 438


def test_ring_contract(open_page):
    page = open_page(SAMPLE)
    result = page.evaluate("""async () => {
      const m = await import("/static/rings.js");
      const snap = await (await fetch("/static/fixtures/sample-company.json")).json();
      const el = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      el.setAttribute("class", "rings"); el.setAttribute("viewBox", "0 0 400 400");
      m.buildRings(el, snap, { labels: true });
      const defs = el.querySelector("defs");
      const labels = [...el.querySelectorAll(".label--phase")];
      const d = m.glyphDefs(); const g = m.glyph("verified");
      return {
        n: labels.length,
        one: labels.every(l => l.children.length === 1 && l.firstElementChild.tagName === "textPath"),
        resolved: labels.every(l => { const h = l.firstElementChild.getAttribute("href"); return h.startsWith("#p-") && defs.querySelector(`path[id="${h.slice(1)}"]`) !== null; }),
        texts: labels.map(l => l.textContent),
        arcs: el.querySelectorAll(".arc").length,
        symbols: [...d.querySelectorAll("symbol")].map(s => s.id), hidden: d.getAttribute("aria-hidden"),
        glyph: g.matches('svg.glyph.glyph--verified[aria-hidden="true"][focusable="false"]'), kids: g.children.length,
        use: g.firstElementChild.matches('use[href="#g-verified"]'),
      };
    }""")
    assert result["n"] == 7 and result["one"] and result["resolved"]
    assert result["texts"] == ["kickoff", "plan", "cycle-build", "cycle-verify", "cycle-close", "retro", "cycle-close"]
    assert result["arcs"] == 9
    assert result["symbols"] == ["g-proposed", "g-ready", "g-in_progress", "g-completed", "g-verified", "g-blocked"]
    assert result["hidden"] == "true" and result["glyph"] and result["kids"] == 1 and result["use"]
    count = subprocess.run(["grep", "-c", "is-filtered", "viz/static/rings.css"], cwd=ROOT, capture_output=True, text=True)
    assert int(count.stdout.strip()) >= 1


def test_ring_live_motion(open_page):
    page = open_page("view=now&data=live-active", wait=".rings .arc--live")
    page.evaluate("window.__marker = 1")
    scroll0 = page.evaluate("window.scrollY")
    deg0 = float(page.get_attribute(".arc--live", "data-deg"))
    assert abs(deg0 - 28.9) < 0.05
    breathe = "document.getAnimations().filter(a => a.animationName === 'breathe')"
    assert page.evaluate(f"{breathe}.length") == 1
    assert page.evaluate(f"{breathe}[0].effect.target.classList.contains('edge-halo')")

    # Push and sample in one evaluate so the sampling starts at the push and stays inside 500 ms.
    push_and_sample = """([mutate, match]) => new Promise(resolve => { const next = structuredClone(window.__viz.snapshot); new Function('next', mutate)(next); window.__viz.push(next);
      const t0 = performance.now(); const look = () => {
        const hit = document.getAnimations().filter(a => a.animationName !== 'sweep' && a.effect && a.effect.target && a.effect.target.matches && a.effect.target.matches(match));
        const names = new Set(hit.flatMap(a => a.effect.getKeyframes().flatMap(k => Object.keys(k))));
        ['offset', 'easing', 'composite', 'computedOffset'].forEach(n => names.delete(n));
        if (hit.length || performance.now() - t0 > 500) resolve({ count: hit.length, names: [...names].map(n => n.replace(/[A-Z]/g, c => '-' + c.toLowerCase())) }); else setTimeout(look, 8);
      }; look(); })"""
    probe_event = '{ id: "EVT-20261029060000-probe", ts: next.generated_at, actor: "chief-of-staff", tier: "executive", event: "note", ref: "ITEM-0003", summary: "ring probe", evidence: [], branch: null, cycle: 1, phase: null, run: null, extra: {} }'
    tick_anim = page.evaluate(push_and_sample, [f"next.events.unshift({probe_event}); next.counts.events += 1;", '.tick[data-event="EVT-20261029060000-probe"]'])
    assert tick_anim == {"count": 1, "names": ["transform"]}, tick_anim
    probe = 'g.ring--open .tick[data-event="EVT-20261029060000-probe"]'
    assert page.locator(probe).count() == 1
    assert "tick--executive" in page.get_attribute(probe, "class")
    assert page.locator("g.ring--open .tick").count() == 39
    assert page.evaluate(f"{breathe}.length") == 1 and page.evaluate("window.__marker") == 1
    assert abs(page.evaluate("window.scrollY") - scroll0) <= 2

    arc_anim = page.evaluate(push_and_sample, ['next.activity.phase.since = "2026-10-29T05:30:08Z";', ".arc--live"])
    assert arc_anim == {"count": 1, "names": ["stroke-dashoffset"]}, arc_anim
    deg1 = float(page.get_attribute(".arc--live", "data-deg"))
    assert abs((deg1 - deg0) - 1.0) <= 0.1
    assert page.locator(".arc--live").count() == 1
    assert page.evaluate(f"{breathe}.length") == 1 and page.evaluate("window.__marker") == 1
    assert page.locator(probe).count() == 1
    assert abs(page.evaluate("window.scrollY") - scroll0) <= 2


def test_gap_closes(open_page):
    page = open_page("view=now&data=live-active", size=PHONE, wait=".waits li.wait")
    page.evaluate("window.__marker = 1")
    page.locator(".waits li.wait").nth(1).scroll_into_view_if_needed()
    page.evaluate("window.scrollTo(0, document.querySelectorAll('.waits li.wait')[1].getBoundingClientRect().top + window.scrollY - 80)")
    scroll0 = page.evaluate("window.scrollY")
    page.evaluate("""() => { window.__cut = document.querySelector('li.wait[data-key="Q-0001"]').getBoundingClientRect().bottom; window.__before = new Map(); document.querySelectorAll('body *').forEach((e, i) => { e.__i = i; window.__before.set(e, e.getBoundingClientRect().toJSON()); }); }""")
    page.evaluate("""() => { const next = structuredClone(window.__viz.snapshot); next.waiting = next.waiting.filter(w => w.key !== "Q-0001"); next.counts.ceo_questions_open -= 1;
      window.__seen = { arcs: 0, ticks: 0, waits: 0 };
      const poll = () => { const now = { arcs: new Set(), ticks: new Set(), waits: new Set() };
        document.getAnimations().forEach(a => { const t = a.effect && a.effect.target; if (!t || !t.classList || ['breathe', 'sweep', 'beacon'].includes(a.animationName)) return;
          if (t.classList.contains('arc')) now.arcs.add(t); if (t.classList.contains('tick')) now.ticks.add(t); if (t.classList.contains('wait')) now.waits.add(t); });
        for (const k of Object.keys(now)) window.__seen[k] = Math.max(window.__seen[k], now[k].size); };
      window.__poll = setInterval(poll, 10); window.__viz.push(next); poll(); }""")
    page.wait_for_function("""() => !document.querySelector('li.wait[data-key="Q-0001"]') && !document.querySelector('.gap-pin[data-key="Q-0001"]')""", timeout=1000)
    seen = page.evaluate("() => { clearInterval(window.__poll); return window.__seen; }")
    assert seen["arcs"] <= 1 and seen["ticks"] <= 8 and seen["waits"] <= 3
    page.wait_for_timeout(600)
    assert page.locator(".rings .gap-pin").count() == 3
    assert text(page, ".waiting .count") == "3" and text(page, ".nav__count") == "3"
    assert page.evaluate("window.__marker") == 1
    assert abs(page.evaluate("window.scrollY") - scroll0) <= 2
    moved = page.evaluate("""() => { const out = []; const cards = [...document.querySelectorAll('li.wait')];
      for (const [e, b] of window.__before) { if (!e.isConnected) continue; if (cards.some(c => c.contains(e))) continue;
        if (e.closest('.horizon')) continue;
        if (b.top >= window.__cut - 1) continue; const r = e.getBoundingClientRect();
        if (Math.abs(r.top - b.top) > 2 || Math.abs(r.left - b.left) > 2) out.push(e.tagName + "." + e.className); } return out; }""")
    assert moved == [], moved


def test_gap_closes_end_frame(open_page, tmp_path):
    """Motion 3 end frame at 390x844, scrollY 0: three pins, the open section smaller, ring arcs eased with --ease-seal."""
    page = open_page("view=now&data=live-active", size=PHONE, wait=".rings .gap-pin")
    assert page.evaluate("window.scrollY") == 0
    span = """() => { const [a, b] = ['start', 'end'].map(k => document.querySelector(`.gap-cap[data-cap="${k}"]`));
      return Math.hypot(+a.getAttribute('x1') - +b.getAttribute('x1'), +a.getAttribute('y1') - +b.getAttribute('y1')); }"""
    before = page.evaluate(span)
    assert page.locator(".rings .gap-pin").count() == 4
    seal = page.evaluate("getComputedStyle(document.querySelector('.ring--open .arc:not(.arc--live)')).transitionTimingFunction")
    assert "0.3, 0, 0.1, 1" in seal, seal
    page.evaluate("""() => { const next = structuredClone(window.__viz.snapshot); next.waiting = next.waiting.filter(w => w.key !== "Q-0001"); next.counts.ceo_questions_open -= 1; window.__viz.push(next); }""")
    page.wait_for_timeout(700)
    assert page.evaluate("window.scrollY") == 0
    assert page.locator(".rings .gap-pin").count() == 3
    assert page.evaluate(span) < before
    shot = tmp_path / "gap-closes-end-phone.png"
    page.screenshot(path=str(shot))
    assert shot.stat().st_size > 0


def _push_run_complete(page):
    return page.evaluate("""() => { const next = structuredClone(window.__viz.snapshot);
      next.activity.phase.status = "idle"; next.activity.phase.name = null; next.activity.phase.since = null; next.activity.agents = [];
      next.events.unshift({ id: "EVT-20261029060100-done", ts: next.generated_at, actor: "talos-run", tier: "mechanical", event: "run.completed", ref: "cycle-build", summary: "done", evidence: [], branch: null, cycle: 1, phase: "cycle-build", run: "EVT-20261029060100-done", extra: { phase: "cycle-build", cost_usd: 1.0 } });
      next.counts.events += 1; window.__viz.push(next);
      const live = document.querySelector('.arc--ending'); const grey = document.querySelector('.arc[data-run="EVT-20261029060100-done"]');
      return { live: !!live, leaving: live ? live.hasAttribute('data-leaving') : null, grey: !!grey, greyLive: grey ? grey.classList.contains('arc--live') : null }; }""")


def test_run_complete_crossfade(open_page):
    """Motion 7: the live path fades out while the grey path of the finished run fades in, then the live path is removed."""
    page = open_page("view=now&data=live-active", wait=".rings .arc--live")
    first = _push_run_complete(page)
    assert first == {"live": True, "leaving": True, "grey": True, "greyLive": False}, first
    page.wait_for_timeout(60)
    assert page.evaluate("document.querySelectorAll('.arc--ending, .arc[data-run=\"EVT-20261029060100-done\"]').length") == 2
    page.wait_for_timeout(500)
    assert page.locator(".arc--ending").count() == 0 and page.locator(".arc--live").count() == 0
    assert page.evaluate("getComputedStyle(document.querySelector('.arc[data-run=\"EVT-20261029060100-done\"]')).opacity") == "1"


def test_halo_finishes_loop(open_page):
    """Motion 6: when activity ends the halo finishes its current breathe loop before the edge is removed."""
    page = open_page("view=now&data=live-active", wait=".rings .edge-halo")
    page.evaluate("""() => { const next = structuredClone(window.__viz.snapshot); next.activity.phase.status = "idle"; next.activity.agents = []; window.__viz.push(next); }""")
    page.wait_for_timeout(1000)
    assert page.locator(".rings .edge-halo").count() == 1  # still breathing, mid loop
    page.wait_for_selector(".rings g.edge", state="detached", timeout=5000)


@pytest.mark.parametrize("command", ["echo hi\u001b[31m", "echo hi\u202e", "echo\u200bhi", "echo hi\ufeff", "echo\u2066hi"])
def test_command_control_chars_and_empty_ref(open_page, command):
    page = open_page("view=now&data=live-active&motion=reduce", wait="li.wait")
    page.evaluate("""(command) => { const next = structuredClone(window.__viz.snapshot);
      const q = next.waiting.find(w => w.kind === "question"); q.ref = ""; q.command = command; window.__viz.push(next); }""", command)
    li = page.locator("li.wait[data-key]").filter(has=page.locator(".wait__kind", has_text="Question")).first
    assert li.locator(".btn:visible").count() == 0 and li.locator(".cmd__hint").count() == 0
    assert li.locator(".wait__meta code").count() == 0


def test_first_paint_static(open_page):
    """Reduced motion: the first paint is the end frame, nothing moves."""
    page = open_page("view=now&data=live-active&motion=reduce", wait=".rings .arc")
    page.wait_for_timeout(300)
    assert page.evaluate("document.getAnimations().filter(a => a.playState === 'running' && a.effect && a.effect.getComputedTiming().duration > 0).length") == 0


def test_first_paint_grows_in(open_page):
    """Full motion: the rings turn into place, oldest first, then settle."""
    page = open_page("view=now&data=live-active", wait=".rings .arc")
    assert page.evaluate("document.getAnimations().filter(a => a.animationName === 'ring-in').length") >= 1
    page.wait_for_function("!document.querySelector('svg.rings.is-intro')", timeout=4000)
    assert page.evaluate("document.getAnimations().filter(a => a.animationName === 'breathe').length") == 1


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("data", ["sample-company", "live-active"])
def test_phone_fit(open_page, scheme, data):
    page = open_page(f"view=now&data={data}&motion=reduce", size=PHONE, scheme=scheme)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.evaluate("document.querySelector('.horizon').getBoundingClientRect().height") == 320
    for sel in ("#edge-h", "#waiting-h"):
        assert page.evaluate(f"document.querySelector('{sel}').getBoundingClientRect().top") < 844


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_overflow_and_unicode(open_page, scheme):
    page = open_page("view=now&data=live-active&motion=reduce", size=PHONE, scheme=scheme)
    page.evaluate(push_js("""
      next.events[0].summary = "x".repeat(300); next.waiting[0].title = "§ é 漢字 <b>x</b>"; next.waiting[0].kind = "question";
    """))
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert "§ é 漢字 <b>x</b>" in page.locator(".waits li.wait .wait__title").first.inner_text()
    assert "x" * 300 in page.locator(".summaries").inner_text()
    assert page.locator(".wait__title b").count() == 0


def test_phone_without_clipboard(open_page):
    page = open_page(SAMPLE, size=PHONE, init_script="delete Navigator.prototype.clipboard; Object.defineProperty(navigator, 'clipboard', { value: undefined });", clipboard=False)
    cmds = page.locator(".cmd")
    assert cmds.count() == 2
    for i in range(2):
        assert "select to copy" in cmds.nth(i).inner_text()
        assert cmds.nth(i).locator("button").is_hidden()


def test_idempotent_push(open_page):
    page = open_page("view=now&data=live-active&motion=reduce")
    before = page.evaluate("document.body.innerHTML")
    page.evaluate("window.__viz.push(structuredClone(window.__viz.snapshot)); window.__viz.push(structuredClone(window.__viz.snapshot))")
    page.wait_for_timeout(100)
    assert page.evaluate("document.body.innerHTML") == before
    assert page.evaluate("document.querySelectorAll('[data-entering], [data-leaving]').length") == 0


def test_keyboard_walk(open_page):
    page = open_page("view=now&data=live-active&motion=reduce")
    seen, bad = [], []
    page.keyboard.press("Tab")
    for _ in range(40):
        if page.evaluate("document.activeElement.tagName") == "BODY" and seen:
            break
        info = page.evaluate("""() => { const a = document.activeElement; const cs = getComputedStyle(a);
          return { key: a.tagName + '|' + (a.getAttribute('href') || a.textContent.trim().slice(0, 20)) + '|' + [...document.querySelectorAll('a, button, select, summary, input')].indexOf(a), ok: cs.outlineStyle !== 'none' }; }""")
        if info["key"] in seen:
            break
        seen.append(info["key"])
        if not info["ok"]:
            bad.append(info["key"])
        page.keyboard.press("Tab")
    visible = page.evaluate("""() => [...document.querySelectorAll('a, button, select, summary, input')].map((e, i) => [e, i]).filter(([e]) => !e.closest('[hidden]') && e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden').map(([e, i]) => e.tagName + '|' + (e.getAttribute('href') || e.textContent.trim().slice(0, 20)) + '|' + i)""")
    assert bad == []
    assert set(seen) == set(visible)


def test_edge_dots_distinct(open_page):
    """ADR-0005 amendment 5: concurrent writers fan back along the live arc at least 4.5 degrees apart."""
    page = open_page(ACTIVE, wait=".rings .edge-tip")
    rotations = page.evaluate("[...document.querySelectorAll('.rings g.edge-agent')].map(g => g.style.transform)")
    assert rotations == ["rotate(-0.5deg)", "rotate(-5deg)", "rotate(-15.94deg)"]
    centres = page.evaluate("""[...document.querySelectorAll('.rings .edge-dot')].map(c => { const b = c.getBoundingClientRect();
      return [b.x + b.width / 2, b.y + b.height / 2]; })""")
    for i in range(len(centres)):
        for j in range(i + 1, len(centres)):
            d = ((centres[i][0] - centres[j][0]) ** 2 + (centres[i][1] - centres[j][1]) ** 2) ** 0.5
            assert d >= 15, f"dots {i} and {j} overlap: {d:.1f} px apart"
    # A minimum live arc (6 degrees) clamps the fan at the arc's start instead of drawing behind it.
    page.evaluate("""() => { const next = structuredClone(window.__viz.snapshot);
      next.activity.phase.since = next.generated_at; window.__viz.push(next); }""")
    page.wait_for_function("document.querySelector('.rings .arc--live').dataset.deg === '6.0'")
    rotations = page.evaluate("[...document.querySelectorAll('.rings g.edge-agent')].map(g => g.style.transform)")
    assert rotations == ["rotate(-0.5deg)", "rotate(-5deg)", "rotate(-6deg)"]


### ---- ITEM-0016 (SPEC-0010): the headline and the chips never claim more than the deriver knows ----
import os
import shutil
import sys
import time

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PHASES = {"kickoff", "plan", "review", "cycle-build", "cycle-verify", "cycle-close", "retro", "status"}
CASES = ROOT.parents[2] / "tests" / "viz" / "fixtures" / "transcripts"
CASE_NAMES = sorted(p.name for p in CASES.iterdir() if p.is_dir())
CYCLE_2_CLOSED = {"number": 2, "open": False, "budget": "150 minutes wall-clock for the whole loop",
                  "started_at": "2026-10-29T14:50:00Z", "ended_at": "2026-10-29T15:37:19Z", "elapsed_minutes": 47}


def derived_activity(tmp_path, case, age):
    """The activity block viz.activity.derive() gives for a copy of a committed transcript case aged `age` seconds."""
    from viz import activity

    copy = tmp_path / case
    shutil.copytree(CASES / case, copy)
    when = time.time() - age
    for p in copy.rglob("*"):
        if p.is_file():
            os.utime(p, (when, when))
    ledger_path = CASES / f"{case}.ledger.jsonl"
    if not ledger_path.is_file():
        ledger_path = ROOT.parents[2] / "tests" / "viz" / "fixtures" / "sample-company" / "ledger.jsonl"
    with open(ledger_path, encoding="utf-8") as f:
        ledger = [json.loads(line) for line in f if line.strip()]
    return activity.derive(tmp_path, tmp_path / "company", ledger, 2, override=str(copy))


def push_activity(page, act, cycle=None):
    page.evaluate("""([act, cycle]) => { const next = structuredClone(window.__viz.snapshot); next.activity = act;
      if (cycle) next.cycle = cycle; window.__viz.push(next); }""", [act, cycle])
    page.wait_for_timeout(100)


def chip_texts(page):
    return page.evaluate("""[...document.querySelectorAll('li.agent')].map(li => [li.querySelector('.agent__name').textContent,
      li.querySelector('.agent__on').textContent.trim(), li.querySelector('.agent__on').hidden])""")


def test_closed_15_43_headline_and_labels(open_page, tmp_path):
    page = open_page(IDLE)
    push_activity(page, derived_activity(tmp_path, "closed-15-43", 50), CYCLE_2_CLOSED)
    assert text(page, "h1#phase") == "Idle"
    meta = text(page, ".phase__meta")
    assert meta.startswith("cycle 2 · closed") and "last: cycle-close" in meta
    chips = chip_texts(page)
    assert sorted(name for name, _, _ in chips) == ["chief-of-staff", "head-of-product", "librarian", "main session"]
    for name, on, hidden in chips:
        assert on not in ("on ITEM-0004", "on ITEM-0003", "on ITEM-0013")
        assert "transcript" not in on and "transcript" not in name
        assert on == "" and hidden is True
    assert page.errors == []


def test_engineer_active_labels_keep_charter_4(open_page, tmp_path):
    page = open_page(IDLE)
    push_activity(page, derived_activity(tmp_path, "engineer-active", 30))
    chips = [(name, on) for name, on, _ in chip_texts(page)]
    assert ("engineer", "on ITEM-0003") in chips
    assert ("main session", "on cycle-build") in chips
    assert " ".join(text(page, "h1#phase").split()) == "Running build"


def test_launcher_verify_headline(open_page, tmp_path):
    page = open_page(IDLE)
    push_activity(page, derived_activity(tmp_path, "launcher-verify", 30))
    assert " ".join(text(page, "h1#phase").split()) == "Running verify"
    assert page.locator("h1#phase code").get_attribute("data-phase") == "cycle-verify"


@pytest.mark.parametrize("source", CASE_NAMES + ["data:live-active", "data:live-idle"])
def test_never_a_nameless_run(open_page, tmp_path, source):
    if source.startswith("data:"):
        page = open_page(f"view=now&data={source[5:]}&motion=reduce")
    else:
        page = open_page(IDLE)
        push_activity(page, derived_activity(tmp_path, source, 30))
    headline = text(page, "h1#phase")
    if headline.startswith("Running"):
        assert page.locator("h1#phase code").get_attribute("data-phase") in PHASES
    assert page.errors == []
