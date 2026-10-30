// Timeline view (SPEC-0004; components.md Filters, Cycle heading, Phase group, Event row, The rings).
// mount builds the static structure once; update reconciles keyed nodes (cycle:<n>, run id, event id) and never rebuilds the root.
import { buildRings, updateRings } from "../rings.js";
import { attachInspector, legend } from "../inspect.js";

export const id = "timeline";
export const title = "Timeline";

const R = new WeakMap();
const TIERS = new Set(["ceo", "executive", "execution", "review", "mechanical"]);
const MAX_ENTERING = 8;

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function put(node, s) {
  s = String(s);
  if (node.textContent !== s) node.textContent = s;
}

// ---------- mount ----------
export function mount(root, ctx) {
  const { h } = ctx;
  root.classList.add("main--split");
  const r = {
    root, built: false, svg: null, ringSig: "", actor: "", type: "", srSig: "", restSig: "", smallSig: "",
    sections: new Map(), groups: new Map(), rows: new Map(), events: [], snap: null, openAll: ctx.params.get("open") === "all",
  };

  r.k = h("span", { class: "k" }, "0");
  r.small = h("small");
  r.centre = h("div", { class: "rings__centre" }, h("p", { class: "rings__count" }, r.k, r.small));
  r.sr = h("p", { class: "sr-only" });
  r.stage = h("div", { class: "stage" }, r.centre, r.sr);

  r.actorSel = h("select", { class: "select", name: "actor" });
  r.typeSel = h("select", { class: "select", name: "type" });
  r.num = h("span", { class: "num", "aria-live": "polite" }, "0");
  r.rest = h("span");
  r.clear = h("button", { type: "button", class: "link-btn", disabled: true }, "Clear");
  r.filters = h("form", { class: "filters", "aria-label": "Filter events" },
    h("label", {}, "Actor", r.actorSel),
    h("label", {}, "Event type", r.typeSel),
    h("p", { class: "filters__count" }, h("span", {}, r.num, r.rest), r.clear));
  r.ledger = h("div", { class: "ledger" });

  root.append(
    h("h1", { class: "sr-only" }, "Timeline"),
    h("div", { class: "picture picture--map" }, r.stage),
    h("div", { class: "panel" }, r.filters, r.ledger));

  r.filters.addEventListener("submit", (e) => e.preventDefault());
  const onChange = () => {
    r.actor = r.actorSel.value;
    r.type = r.typeSel.value;
    ctx.setParam("actor", r.actor || null);
    ctx.setParam("type", r.type || null);
    applyFilter(r, ctx, false);
  };
  r.actorSel.addEventListener("change", onChange);
  r.typeSel.addEventListener("change", onChange);
  r.clear.addEventListener("click", () => {
    r.actorSel.value = "";
    r.typeSel.value = "";
    onChange();
  });

  // toggle does not bubble: listen in the capture phase on the ledger.
  r.ledger.addEventListener("toggle", (e) => {
    const g = e.target;
    if (!(g instanceof Element) || !g.classList.contains("group")) return;
    if (g._sys !== undefined && g._sys === g.open) g._sys = undefined;
    else {
      g._want = g.open;
      if (g.open) staggerIn(g, ctx);
    }
    hintOf(g);
    syncOpen(r);
  }, true);

  // An EVT anchor whose row sits in a closed group opens that group before the default jump.
  r.ledger.addEventListener("click", (e) => {
    const a = e.target instanceof Element ? e.target.closest('a[href^="#EVT-"]') : null;
    if (!a) return;
    let target = null;
    try {
      target = document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)));
    } catch {
      target = null;
    }
    const g = target && target.closest("details.group");
    if (g && !g.open) g.open = true;
  });

  R.set(root, r);
}

// Motion 10: on a user expand the first 8 visible rows fade in, each --stagger after the previous; later rows just show.
function staggerIn(g, ctx) {
  const rows = [...g._ol.children].filter((li) => !li.hidden).slice(0, MAX_ENTERING);
  rows.forEach((li, i) => {
    if (i) li.setAttribute("data-stagger", String(i));
    ctx.motion.enter(li);
  });
  const total = ctx.motion.durationMs("--dur-2") + 7 * ctx.motion.durationMs("--stagger");
  setTimeout(() => rows.forEach((li) => li.removeAttribute("data-stagger")), total + 20);
}

// ADR-0005 amendment 6: a binned tick carries its oldest member's id and data-count; its members are the next
// data-count events of the same run (run-null events of one cycle count as one run), oldest first.
function binMembers(r, id, count) {
  const li = r.rows.get(id);
  if (!li) return [id];
  const ev = li._ev;
  const run = ev.run || null;
  const ordered = (r.snap.events || []).filter((e) => e.cycle === ev.cycle && (e.run || null) === run).reverse();
  const i = ordered.findIndex((e) => e.id === id);
  return i < 0 ? [id] : ordered.slice(i, i + count).map((e) => e.id);
}

// ---------- model ----------
function model(snap) {
  const events = snap.events || [];
  const cycles = new Map();
  const used = new Set();
  const runs = new Set();
  for (const ev of events) {
    if (ev.run) runs.add(ev.run);
    let c = cycles.get(ev.cycle);
    if (!c) {
      c = { n: ev.cycle, groups: [], events: [] };
      cycles.set(ev.cycle, c);
    }
    c.events.push(ev);
    const key = ev.run || `current:${ev.cycle}`;
    let g = c.groups[c.groups.length - 1];
    if (!g || g.base !== key) {
      let unique = key;
      for (let i = 2; used.has(`${c.n}|${unique}`); i++) unique = `${key}~${i}`;
      used.add(`${c.n}|${unique}`);
      g = { key: unique, base: key, phase: ev.run ? ev.phase || "" : "current", events: [] };
      c.groups.push(g);
    }
    g.events.push(ev);
  }
  const cur = snap.cycle && Number.isFinite(snap.cycle.number) ? snap.cycle.number : 0;
  if (!cycles.size) cycles.set(cur, { n: cur, groups: [], events: [] });
  const list = [...cycles.values()].sort((a, b) => b.n - a.n);
  const nums = new Set(cycles.keys());
  nums.add(cur);
  return { cycles: list, newest: list[0].n, nCycles: nums.size, nRuns: runs.size, total: events.length };
}

// ---------- building blocks ----------
function buildRow(ev, ctx) {
  const { h, fmt } = ctx;
  const tier = TIERS.has(ev.tier) ? ev.tier : "executive";
  const refs = [];
  for (const raw of ev.evidence || []) {
    const ref = String(raw);
    if (refs.length) refs.push(" ");
    refs.push(/^EVT-/.test(ref) ? h("a", { href: `#${ref}` }, ref) : h("code", {}, ref));
  }
  return h("li", { class: `event event--${tier}`, id: ev.id, "data-key": ev.id },
    h("span", { class: "tick", "aria-hidden": "true" }),
    h("p", { class: "event__line" },
      h("time", {}, fmt.clock(ev.ts)), " ",
      h("span", { class: "event__actor" }, ev.actor), " ",
      h("code", { class: "event__type" }, ev.event),
      ev.ref ? [" ", h("span", { class: "event__ref" }, ev.ref)] : null),
    h("p", { class: "event__summary" }, ev.summary),
    refs.length ? h("p", { class: "event__refs" }, h("span", { class: "label" }, "evidence"), " ", refs) : null);
}

function buildGroup(key, cycle, want, ctx) {
  const { h } = ctx;
  const phase = h("span", { class: "group__phase" });
  const count = h("span", { class: "group__count" });
  const span = h("span", { class: "group__span" });
  const sum = h("summary", { class: "group__sum" }, phase, " ", count, " ", span);
  const ol = h("ol", { class: "events" });
  const g = h("details", { class: "group", "data-key": key, open: want }, sum, ol);
  Object.assign(g, { _key: key, _cycle: cycle, _want: want, _sys: undefined, _sum: sum, _phase: phase, _count: count, _span: span, _ol: ol, _hint: null, _h: h });
  return g;
}

function buildSection(n, ctx) {
  const { h } = ctx;
  const name = n === 0 ? "Cycle 0 (planning)" : `Cycle ${n}`;
  const meta = h("span", { class: "cycle-h__meta" });
  const h2 = h("h2", { id: `c${n}`, class: "cycle-h" }, name, " ", meta);
  const node = h("section", { "aria-labelledby": `c${n}`, "data-key": `cycle:${n}` }, h2);
  return { n, node, h2, meta, m: 0, first: "", last: "" };
}

// Put `node` before `ref` unless it already is `ref`; returns the next reference sibling.
function place(container, node, ref, quiet, ctx) {
  if (node === ref) return ref.nextSibling;
  if (quiet || !container.isConnected || node.isConnected) container.insertBefore(node, ref);
  else ctx.motion.insertKeepingScroll(container, node, ref);
  return ref;
}

// ---------- reconcile ----------
function reconcile(r, snap, ctx, first) {
  const m = model(snap);
  r.model = m;
  r.snap = snap;
  const want = new Set((snap.events || []).map((e) => e.id));
  for (const [rid, li] of r.rows) {
    if (!want.has(rid)) {
      li.remove();
      r.rows.delete(rid);
    }
  }
  const claimedGroups = new Set();
  const claimedSections = new Set();
  const entering = [];
  let secRef = r.ledger.firstChild;

  for (const cyc of m.cycles) {
    let sec = r.sections.get(cyc.n);
    const secNew = !sec;
    if (secNew) {
      sec = buildSection(cyc.n, ctx);
      r.sections.set(cyc.n, sec);
    }
    claimedSections.add(sec);
    sec.m = cyc.events.length;
    sec.last = cyc.events.length ? cyc.events[0].ts : "";
    sec.first = cyc.events.length ? cyc.events[cyc.events.length - 1].ts : "";
    let gRef = sec.h2.nextSibling;

    for (const grp of cyc.groups) {
      let g = r.groups.get(grp.key);
      if (g && (claimedGroups.has(g) || g._cycle !== cyc.n)) g = null;
      if (!g) {
        // A run completed: the group holding these rows keeps its node and takes the new key.
        for (const ev of grp.events) {
          const li = r.rows.get(ev.id);
          const cand = li && li.closest("details.group");
          if (cand && !claimedGroups.has(cand) && cand._cycle === cyc.n) {
            g = cand;
            break;
          }
        }
        if (g) {
          if (r.groups.get(g._key) === g) r.groups.delete(g._key);
          g._key = grp.key;
          g.setAttribute("data-key", grp.key);
          r.groups.set(grp.key, g);
        }
      }
      const gNew = !g;
      if (gNew) {
        g = buildGroup(grp.key, cyc.n, r.openAll || cyc.n === m.newest, ctx);
        r.groups.set(grp.key, g);
      }
      claimedGroups.add(g);
      put(g._phase, grp.phase);
      put(g._span, `${ctx.fmt.clock(grp.events[grp.events.length - 1].ts)} to ${ctx.fmt.clock(grp.events[0].ts)}`);

      let rowRef = g._ol.firstChild;
      for (const ev of grp.events) {
        let li = r.rows.get(ev.id);
        const isNew = !li;
        if (isNew) {
          li = buildRow(ev, ctx);
          r.rows.set(ev.id, li);
        }
        li._ev = ev;
        rowRef = place(g._ol, li, rowRef, first || gNew || secNew, ctx);
        if (isNew && !first && !gNew && !secNew) entering.push(li);
      }
      gRef = place(sec.node, g, gRef, first || secNew, ctx);
      if (gNew && !first && !secNew) entering.push(g);
    }
    secRef = place(r.ledger, sec.node, secRef, first, ctx);
    if (secNew && !first) entering.push(sec.node);
  }

  for (const [key, g] of r.groups) {
    if (!claimedGroups.has(g)) {
      g.remove();
      r.groups.delete(key);
    }
  }
  for (const [n, sec] of r.sections) {
    if (!claimedSections.has(sec)) {
      sec.node.remove();
      r.sections.delete(n);
    }
  }
  entering.slice(0, MAX_ENTERING).forEach((node) => ctx.motion.enter(node));
}

// ---------- the rings ----------
function renderRings(r, snap, ctx) {
  const sig = JSON.stringify([snap.cycle, (snap.events || []).map((e) => `${e.id}|${e.run}|${e.cycle}`), (snap.waiting || []).map((w) => w.key)]);
  if (!r.svg) {
    const el = ctx.svg("svg", { class: "rings", viewBox: "0 0 400 400", "aria-hidden": "true", focusable: "false" });
    buildRings(el, snap, { labels: true });
    r.stage.insertBefore(el, r.stage.firstChild);
    r.svg = el;
    attachInspector(r.stage, el, ctx);
    r.stage.after(legend(el, ctx, { live: false }));
  } else if (sig !== r.ringSig) {
    updateRings(r.svg, snap, ctx.diff, { labels: true });
  }
  r.ringSig = sig;
  syncHighlights(r, ctx);
}

// One highlight path per arc, kept in a group of its own so the rings reconciler never sees it.
function syncHighlights(r, ctx) {
  for (const ring of r.svg.querySelectorAll(":scope > g.ring")) {
    let hg = ring.querySelector(":scope > g.arcs-hi");
    if (!hg) {
      hg = ctx.svg("g", { class: "arcs-hi" });
      ring.insertBefore(hg, ring.querySelector(":scope > g.ticks"));
    }
    const have = new Map([...hg.children].map((p) => [p.getAttribute("data-run"), p]));
    const seen = new Set();
    for (const arc of ring.querySelectorAll(":scope > g.arcs > path.arc[data-run]")) {
      if (arc.hasAttribute("data-leaving")) continue;
      const run = arc.getAttribute("data-run");
      seen.add(run);
      let p = have.get(run);
      if (!p) {
        p = ctx.svg("path", { class: "arc-hi", "data-run": run });
        hg.append(p);
      }
      // Mirror the arc's geometry (path data, rotation, drawn length) without its class or data attributes.
      for (const { name, value } of arc.attributes) {
        if (name === "class" || name.startsWith("data-")) continue;
        if (p.getAttribute(name) !== value) p.setAttribute(name, value);
      }
      if (p.style.cssText !== arc.style.cssText) p.style.cssText = arc.style.cssText;
    }
    for (const [run, p] of have) if (!seen.has(run)) p.remove();
  }
  syncOpen(r);
}

function syncOpen(r) {
  if (!r.svg) return;
  for (const ring of r.svg.querySelectorAll(":scope > g.ring")) {
    const cyc = Number(ring.getAttribute("data-cycle"));
    for (const p of ring.querySelectorAll(":scope > g.arcs-hi > path.arc-hi")) {
      const run = p.getAttribute("data-run");
      let g = r.groups.get(run);
      if (!g && run === "running") g = r.groups.get(`current:${cyc}`);
      p.classList.toggle("is-open", !!(g && g.open));
    }
  }
}

// ---------- filters ----------
function fillOptions(sel, values, label, current, h) {
  const sig = JSON.stringify([label, values]);
  if (sel._sig !== sig) {
    sel._sig = sig;
    const opts = [h("option", { value: "" }, `${label} (${values.length})`)];
    for (const v of values) opts.push(h("option", { value: v }, v));
    sel.replaceChildren(...opts);
  }
  sel.value = values.includes(current) ? current : "";
  return sel.value;
}

function hintOf(g) {
  const show = !g.open && !g.classList.contains("is-filtered-out") && g._types && g._types.length > 0;
  const text = show ? g._types.join(" · ") : null;
  if (text === null) {
    if (g._hint) {
      g._hint.remove();
      g._hint = null;
    }
    return;
  }
  if (!g._hint) {
    g._hint = g._h("span", { class: "group__hint" });
    g._sum.append(g._hint);
  }
  put(g._hint, text);
}

function range(first, last, ctx) {
  return first ? `${ctx.fmt.clock(first)} to ${ctx.fmt.clock(last)}` : "";
}

function applyFilter(r, ctx, first) {
  const { h, motion } = ctx;
  const snap = r.snap;
  const m = r.model;
  const { actor, type } = r;
  const filtered = !!(actor || type);
  const tickTo = (node, s) => (first ? put(node, s) : motion.tick(node, s));
  const visible = new Set();
  const visibleRuns = new Set();
  const perCycle = new Map();

  for (const g of r.groups.values()) {
    let k = 0;
    const types = [];
    for (const li of g._ol.children) {
      const ev = li._ev;
      const vis = (!actor || ev.actor === actor) && (!type || ev.event === type);
      if (li.hidden === vis) li.hidden = !vis;
      if (vis) {
        k++;
        visible.add(ev.id);
        visibleRuns.add(ev.run || `current:${ev.cycle}`);
        if (!types.includes(ev.event)) types.push(ev.event);
      }
    }
    const total = g._ol.children.length;
    const out = filtered && k === 0;
    g.classList.toggle("is-filtered-out", out);
    const wantOpen = out ? false : g._want;
    if (g.open !== wantOpen) {
      g._sys = wantOpen;
      g.open = wantOpen;
    }
    tickTo(g._count, filtered ? `${k} of ${total}` : `${total}`);
    g._types = types;
    hintOf(g);
    perCycle.set(g._cycle, (perCycle.get(g._cycle) || 0) + k);
  }

  for (const sec of r.sections.values()) {
    const k = perCycle.get(sec.n) || 0;
    const out = filtered && k === 0 && sec.m > 0;
    sec.h2.classList.toggle("is-filtered-out", out);
    let meta;
    if (sec.m === 0) meta = "0 events";
    else if (filtered) meta = `${k} of ${sec.m} events match · ${range(sec.first, sec.last, ctx)}`;
    else {
      meta = `${sec.m} events · ${range(sec.first, sec.last, ctx)}`;
      const c = snap.cycle || {};
      if (c.number === sec.n) {
        if (c.open) meta += " · open";
        else if (c.elapsed_minutes !== null && c.elapsed_minutes !== undefined) meta += ` · ended, ${ctx.fmt.hm(c.elapsed_minutes)}`;
      }
    }
    put(sec.meta, meta);
  }

  // Motion 9: the DOM is already filtered; the list dips to 0.4 over --dur-1 and returns over --dur-2.
  if (!first && motion.durationMs("--dur-1") > 0) {
    r.ledger.setAttribute("data-filtering", "");
    clearTimeout(r.dipTimer);
    r.dipTimer = setTimeout(() => r.ledger.removeAttribute("data-filtering"), motion.durationMs("--dur-1"));
  }

  // ticks on the map (motion 9: one class change on the svg, then the match flags)
  if (r.svg) {
    r.svg.classList.toggle("is-filtered", filtered);
    for (const tick of r.svg.querySelectorAll(".tick[data-event]")) {
      let match = false;
      if (filtered) {
        const tid = tick.getAttribute("data-event");
        match = visible.has(tid);
        if (!match && tick.hasAttribute("data-count")) match = binMembers(r, tid, Number(tick.getAttribute("data-count"))).some((mid) => visible.has(mid));
      }
      if (tick.classList.contains("is-match") !== match) tick.classList.toggle("is-match", match);
    }
  }

  // counts
  const shown = visible.size;
  const shape = `${m.total}|${actor}|${type}|${m.nCycles}|${m.nRuns}`;
  const who = [];
  if (actor) who.push(["actor", actor]);
  if (type) who.push(["type", type]);
  const tail = () => who.flatMap(([k, v], i) => [i ? " · " : "", `${k} `, h("code", {}, v)]);
  if (r.restSig !== shape) {
    r.restSig = shape;
    const scope = `${plural(m.nCycles, "cycle")} · ${plural(m.nRuns, "run")}`;
    r.rest.replaceChildren(...(filtered ? [` of ${m.total} events · `, ...tail()] : [` of ${m.total} events · ${scope}`]));
    r.small.replaceChildren(...(filtered ? [`of ${m.total} events · `, ...tail()] : [`events · ${scope}`]));
  }
  tickTo(r.num, String(shown));
  tickTo(r.k, String(shown));
  r.actorSel.classList.toggle("is-set", !!actor);
  r.typeSel.classList.toggle("is-set", !!type);
  r.clear.disabled = !filtered;
  const sr = `Growth rings map: ${plural(m.nCycles, "cycle")}, ${plural(m.nRuns, "run")}, ${m.total} events; the list below is the same data.`;
  if (sr !== r.srSig) {
    r.srSig = sr;
    put(r.sr, sr);
  }
}

// ---------- update ----------
export function update(root, snapshot, ctx) {
  const r = R.get(root);
  const first = !r.built;
  reconcile(r, snapshot, ctx, first);
  renderRings(r, snapshot, ctx);
  r.actor = fillOptions(r.actorSel, snapshot.actors || [], "All actors", ctx.params.get("actor") || "", ctx.h);
  r.type = fillOptions(r.typeSel, snapshot.event_types || [], "All types", ctx.params.get("type") || "", ctx.h);
  applyFilter(r, ctx, first);
  syncOpen(r);
  r.built = true;
}
