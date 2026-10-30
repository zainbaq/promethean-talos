// rings.js: the only file computing ring or glyph geometry (ADR-0005 amendment, components.md "The rings").
// One pure layout step (snapshot -> model) and one reconciler that builds or patches the <svg>.
import { svg } from "./dom.js";
import { enter, durationMs, reduced } from "./motion.js";

const C = 200;
const R_OUT = 170;
const R_STEP = 36;
const FULL_RINGS = 4;
const THIN_FIRST = 46;
const THIN_STEP = 8;
const ARC_GAP = 2;
const ARC_MIN = 12;
const LIVE_MIN = 6;
const TICK_CAP = 360;
const PIN_SLOT = 12;
const PIN_GAP = 4;
const EDGE_DOT_SEP = 4.5; // degrees between neighbouring agent dots (13.35 units at R_OUT, more than a dot's 12-unit diameter)
const MAX_ENTERING_TICKS = 8;
const TICK_LEN = { ceo: 22, executive: 14, execution: 9, review: 9, mechanical: 5 };
const TIER_RANK = { ceo: 4, executive: 3, execution: 2, review: 2, mechanical: 1 };

const r2 = (n) => Math.round(n * 100) / 100;
const f2 = (n) => String(r2(n));

function pt(r, deg) {
  const a = (deg * Math.PI) / 180;
  return [r2(C + r * Math.sin(a)), r2(C - r * Math.cos(a))];
}

function costOf(ev) {
  return Number(ev && ev.extra && ev.extra.cost_usd) || 0;
}

// Arc lengths in degrees: proportional to cost, 12 degree minimum, 2 degrees between arcs, inside `span` degrees.
function distribute(costs, span) {
  const n = costs.length;
  const lens = new Array(n).fill(0);
  if (!n) return lens;
  let room = Math.max(0, span - ARC_GAP * (n - 1));
  let free = costs.map((_, i) => i);
  for (;;) {
    const total = free.reduce((s, i) => s + costs[i], 0);
    const want = (i) => (total > 0 ? (room * costs[i]) / total : room / free.length);
    const low = free.filter((i) => want(i) < ARC_MIN);
    if (!low.length) {
      for (const i of free) lens[i] = want(i);
      return lens;
    }
    for (const i of low) {
      lens[i] = ARC_MIN;
      room -= ARC_MIN;
    }
    room = Math.max(0, room);
    free = free.filter((i) => !low.includes(i));
    if (!free.length) return lens;
  }
}

export function layout(snapshot, opts = {}) {
  const now = opts.now ?? Date.parse(snapshot.generated_at);
  const events = [...(snapshot.events || [])].reverse();
  const cycleInfo = snapshot.cycle || { number: 0, open: false };
  const nums = new Set(events.map((e) => e.cycle));
  nums.add(cycleInfo.number);
  const cycles = [...nums].sort((a, b) => a - b);
  const waiting = snapshot.waiting || [];
  const n = waiting.length;
  const sec = n ? PIN_SLOT * n + PIN_GAP * (n - 1) : 0;
  const act = snapshot.activity || {};
  const running = !!(act.phase && act.phase.status === "running");
  const byId = new Map(events.map((e) => [e.id, e]));
  const costBy = new Map();
  for (const e of events) if (e.event === "run.completed") costBy.set(e.cycle, (costBy.get(e.cycle) || 0) + costOf(e));
  const model = { rings: [], sec, pins: [], edge: null, eventCount: events.length };

  cycles.forEach((c, idx) => {
    const k = cycles.length - 1 - idx;
    const outer = k === 0;
    const full = k < FULL_RINGS;
    const r = full ? R_OUT - R_STEP * k : Math.max(6, THIN_FIRST - THIN_STEP * (k - FULL_RINGS));
    const s = outer ? sec : 0;
    const avail = 360 - s;
    const isOpen = !!cycleInfo.open && cycleInfo.number === c;
    const evs = events.filter((e) => e.cycle === c);
    const runIds = [];
    const runEvents = new Map();
    const nullEvents = [];
    for (const e of evs) {
      if (e.run) {
        if (!runEvents.has(e.run)) {
          runIds.push(e.run);
          runEvents.set(e.run, []);
        }
        runEvents.get(e.run).push(e);
      } else nullEvents.push(e);
    }
    let fill = 1;
    if (isOpen) {
      const prev = costBy.get(c - 1) || 0;
      const spent = Number(snapshot.spend && snapshot.spend.events && snapshot.spend.events.cost_usd) || 0;
      fill = prev > 0 ? Math.min(1, spent / prev) : 0;
    }
    const costs = runIds.map((id) => costOf(byId.get(id)));
    const lens = distribute(costs, isOpen ? fill * avail : avail);
    const arcs = [];
    let a = s / 2;
    runIds.forEach((id, i) => {
      const done = byId.get(id);
      arcs.push({ run: id, start: a, len: lens[i], live: false, phase: (done && done.extra && done.extra.phase) || (done && done.phase) || "", events: runEvents.get(id) });
      a += lens[i] + ARC_GAP;
    });
    const lastEnd = arcs.length ? a - ARC_GAP : s / 2;
    let live = null;
    if (running && isOpen) {
      const since = Date.parse(act.phase.since);
      const minutes = Number.isFinite(since) ? (now - since) / 60000 : 0;
      const start = arcs.length ? a : s / 2;
      const deg = Math.max(0, Math.min(Math.max(LIVE_MIN, minutes), 360 - s / 2 - start));
      live = { run: "running", start, len: deg, live: true, phase: act.phase.name || "", events: nullEvents };
      arcs.push(live);
    }
    // Ticks: evenly spaced along their arc; run-null events without a live arc sit over the 6 degrees after the last arc.
    // A ring with no runs at all (records from before run.completed existed) spreads its events round the whole ring.
    const ticks = [];
    const place = (list, start, len) => list.forEach((e, i) => ticks.push({ id: e.id, tier: e.tier, angle: start + ((i + 0.5) * len) / list.length }));
    for (const arc of arcs) place(arc.events, arc.start, arc.len);
    if (!live && nullEvents.length) {
      if (arcs.length) place(nullEvents, lastEnd + ARC_GAP, 6);
      else place(nullEvents, s / 2, isOpen ? Math.max(6, fill * avail) : avail);
    }
    model.rings.push({
      cycle: c, r, k, full, recent: k < 2, open: isOpen, fill, outer, order: idx,
      label: full ? (isOpen ? `cycle ${c} open` : `cycle ${c}`) : null,
      arcs, ticks: tickShapes(ticks), eventCount: evs.length,
    });
    if (live && outer) {
      const edge = live.start + live.len;
      model.edge = { angle: edge, liveStart: live.start, r, agents: [] };
    }
  });

  waiting.forEach((w, i) => {
    const angle = -sec / 2 + PIN_SLOT / 2 + (PIN_SLOT + PIN_GAP) * i;
    const label = w.kind === "question" ? w.id : w.gate === "release" ? w.ref : w.gate;
    model.pins.push({ key: w.key, angle, label: String(label ?? ""), far: i % 2 === 1 });
  });

  if (model.edge) {
    const edge = model.edge;
    const windowS = act.window_seconds ?? 120;
    // ADR-0005 amendment 5: dots sit at edge - seconds_ago / 16 degrees, each at least EDGE_DOT_SEP behind the
    // previous (latest writer first), never behind the live arc's start, so concurrent writers stay distinct marks.
    const span = edge.angle - edge.liveStart;
    let prev = -Infinity;
    const agents = [...(act.agents || [])].sort((a, b) => (a.seconds_ago || 0) - (b.seconds_ago || 0)).map((ag) => {
      const off = Math.min(Math.max(Math.max(0, ag.seconds_ago || 0) / 16, prev + EDGE_DOT_SEP), span);
      prev = off;
      return {
        key: `${ag.role}|${ag.session || ""}|${ag.transcript || ""}`,
        recent: ag.state ? ag.state === "recent" : (ag.seconds_ago || 0) > windowS,
        off, angle: edge.angle - off,
        text: ag.role,
        sub: ag.item || (act.phase && act.phase.name) || "transcript",
      };
    });
    edge.agents = agents;
  }
  return model;
}

// Over 360 ticks in one ring: bin per degree, a bin of n draws one longer tick (components.md).
function tickShapes(ticks) {
  let list;
  if (ticks.length <= TICK_CAP) {
    list = ticks.map((t) => ({ id: t.id, tier: t.tier, angle: t.angle, count: 1 }));
  } else {
    const bins = new Map();
    for (const t of ticks) {
      const b = Math.floor((((t.angle % 360) + 360) % 360));
      if (!bins.has(b)) bins.set(b, []);
      bins.get(b).push(t);
    }
    list = [...bins.values()].map((m) => ({
      id: m[0].id,
      tier: m.reduce((best, t) => ((TIER_RANK[t.tier] || 2) > (TIER_RANK[best] || 2) ? t.tier : best), m[0].tier),
      angle: m.reduce((s, t) => s + t.angle, 0) / m.length,
      count: m.length,
    }));
  }
  return list.map((t) => ({ ...t, len: t.count > 1 ? Math.min(22, 9 + 2 * t.count) : TICK_LEN[t.tier] ?? 9 }));
}

function setAttrs(el, attrs) {
  for (const [k, v] of Object.entries(attrs)) {
    const s = String(v);
    if (el.getAttribute(k) !== s) el.setAttribute(k, s);
  }
  return el;
}

function find(parent, selector) {
  return parent.querySelector(`:scope > ${selector}`);
}

function ensure(parent, selector, make, animate) {
  let el = find(parent, selector);
  if (!el) {
    el = make();
    parent.append(el);
    if (animate) enter(el);
  }
  return el;
}

function fadeRemove(node, token = "--dur-2") {
  if (node.hasAttribute("data-leaving")) return;
  node.setAttribute("data-leaving", "");
  const ms = durationMs(token);
  if (!ms) node.remove();
  else setTimeout(() => node.remove(), ms + 20);
}

// Reconcile keyed children of `parent`: create missing (entering when animate), patch present, remove vanished.
function sync(parent, items, keyAttr, make, patch, animate, maxEnter = Infinity, drop = (el) => el.remove()) {
  const existing = new Map();
  for (const c of parent.children) if (c.hasAttribute(keyAttr) && !c.hasAttribute("data-leaving")) existing.set(c.getAttribute(keyAttr), c);
  const seen = new Set();
  let entered = 0;
  for (const item of items) {
    const key = String(item.key);
    let el = existing.get(key);
    if (!el) {
      el = make(item);
      parent.append(el);
      if (animate && entered++ < maxEnter) enter(el);
    }
    patch(el, item);
    seen.add(key);
  }
  for (const [k, el] of existing) if (!seen.has(k)) drop(el);
}

function circlePath(r) {
  return `M${C} ${C - r} A${r} ${r} 0 1 1 ${C} ${C + r} A${r} ${r} 0 1 1 ${C} ${C - r}`;
}

function arcAttrs(arc, r) {
  return {
    d: circlePath(r), pathLength: 360, transform: `rotate(${f2(arc.start)} ${C} ${C})`,
    "stroke-dasharray": "360 360",
  };
}

function renderRing(root, ring, opts, animate) {
  const g = ensure(root, `g.ring[data-cycle="${CSS.escape(String(ring.cycle))}"]`, () => svg("g", { "data-cycle": ring.cycle }), false);
  const cls = ["ring", ring.full ? "ring--full" : "ring--thin"];
  if (ring.recent) cls.push("ring--recent");
  if (ring.k === 0) cls.push("ring--latest");
  if (ring.open) cls.push("ring--open");
  setAttrs(g, { class: cls.join(" ") });
  g.style.setProperty("--i", String(ring.order));
  if (ring.open) setAttrs(g, { "data-fill": ring.fill.toFixed(2) });
  else g.removeAttribute("data-fill");
  const track = ensure(g, "circle.track", () => svg("circle", { class: "track", cx: C, cy: C }), false);
  setAttrs(track, { r: ring.r });
  const arcs = ensure(g, "g.arcs", () => svg("g", { class: "arcs" }), false);
  const ticks = ensure(g, "g.ticks", () => svg("g", { class: "ticks" }), false);
  const labels = opts.labels ? ensure(g, "g.labels", () => svg("g", { class: "labels" }), false) : null;
  let cyc = find(g, "text.label--cycle");
  if (ring.label) {
    if (!cyc) {
      cyc = svg("text", { class: "label label--cycle", x: C, "text-anchor": "middle" });
      g.append(cyc);
    }
    setAttrs(cyc, { y: C + ring.r - 13 });
    if (cyc.textContent !== ring.label) cyc.textContent = ring.label;
  } else if (cyc) cyc.remove();

  sync(arcs, ring.arcs.map((a) => ({ ...a, key: a.run })), "data-run",
    (a) => svg("path", { class: "arc", "data-run": a.run }),
    (el, a) => {
      const next = arcAttrs(a, ring.r);
      // Phone cap (motion.md): one arc animates at a time; the others take their new length without a transition.
      const off = `${f2(360 - a.len)}px`;
      const deferred = animate && el.hasAttribute("d") && el.style.strokeDashoffset !== off;
      if (deferred) moving.push({ el, off });
      setAttrs(el, { class: a.live ? "arc arc--live" : "arc", ...next });
      if (!deferred && el.style.strokeDashoffset !== off) el.style.strokeDashoffset = off;
      if (a.live) setAttrs(el, { "data-deg": a.len.toFixed(1) });
    }, animate, 1, (el) => {
      // Motion 7, run complete: the live path stays and fades 1 -> 0 while the grey path of the finished run fades 0 -> 1.
      if (animate && el.classList.contains("arc--live")) {
        el.setAttribute("class", "arc arc--ending");
        el.removeAttribute("data-deg");
        fadeRemove(el, "--dur-2");
      } else el.remove();
    });

  const entering = animate ? MAX_ENTERING_TICKS : 0;
  sync(ticks, ring.ticks.map((t) => ({ ...t, key: t.id })), "data-event",
    (t) => {
      const el = svg("line", { "data-event": t.id });
      if (animate) born.push({ el, ring, t });
      return el;
    },
    (el, t) => {
      el.style.setProperty("--a", (((t.angle % 360) + 360) % 360 / 360).toFixed(3));
      const [x1, y1] = pt(ring.r - t.len / 2, t.angle);
      const [x2, y2] = pt(ring.r + t.len / 2, t.angle);
      setAttrs(el, { class: `tick tick--${t.tier}`, x1, y1, x2, y2 });
      if (t.count > 1) setAttrs(el, { "data-count": t.count });
      else el.removeAttribute("data-count");
    }, animate, entering);

  if (labels) renderPhaseLabels(root, g, labels, ring);
}

function renderPhaseLabels(root, g, labels, ring) {
  let defs = find(root, "defs");
  if (!defs) {
    defs = svg("defs");
    root.prepend(defs);
  }
  const wanted = [];
  ring.arcs.forEach((a, i) => {
    if (a.live || a.len < 18 || !a.phase) return;
    const id = `p-${ring.cycle}-${i}`;
    const mid = a.start + a.len / 2;
    const upper = Math.cos((mid * Math.PI) / 180) >= 0;
    const rr = ring.r + (upper ? 12 : 19);
    const large = a.len > 180 ? 1 : 0;
    const [x1, y1] = pt(rr, upper ? a.start : a.start + a.len);
    const [x2, y2] = pt(rr, upper ? a.start + a.len : a.start);
    wanted.push({ key: id, d: `M${x1.toFixed(2)} ${y1.toFixed(2)} A${rr} ${rr} 0 ${large} ${upper ? 1 : 0} ${x2.toFixed(2)} ${y2.toFixed(2)}`, phase: a.phase });
  });
  const prefix = `p-${ring.cycle}-`;
  for (const p of [...defs.children]) if (p.id.startsWith(prefix) && !wanted.some((w) => w.key === p.id)) p.remove();
  for (const w of wanted) {
    let p = defs.querySelector(`:scope > [id="${CSS.escape(w.key)}"]`);
    if (!p) {
      p = svg("path", { id: w.key });
      defs.append(p);
    }
    setAttrs(p, { d: w.d });
  }
  sync(g.querySelector(":scope > g.labels"), wanted, "data-label",
    (w) => svg("text", { class: "label label--phase", "data-label": w.key }, svg("textPath", { href: `#${w.key}`, startOffset: "50%", "text-anchor": "middle" })),
    (el, w) => {
      const tp = el.firstElementChild;
      if (tp.textContent !== w.phase) tp.textContent = w.phase;
    }, false);
}

function renderGaps(root, model, animate) {
  const gaps = ensure(root, "g.gaps", () => svg("g", { class: "gaps" }), false);
  const half = model.sec / 2;
  const caps = model.pins.length ? [["start", -half], ["end", half]] : [];
  sync(gaps, caps.map(([k, a]) => ({ key: k, angle: a })), "data-cap",
    (c) => svg("line", { class: "gap-cap", "data-cap": c.key }),
    (el, c) => {
      const [x1, y1] = pt(162, c.angle);
      const [x2, y2] = pt(178, c.angle);
      setAttrs(el, { x1, y1, x2, y2 });
    }, animate);
  for (const el of [...gaps.querySelectorAll(":scope > .gap-cap[data-cap]")]) {
    if (!caps.some(([k]) => k === el.getAttribute("data-cap"))) fadeRemove(el);
  }
  const have = new Map([...gaps.children].filter((c) => c.classList.contains("pin") && !c.hasAttribute("data-leaving")).map((c) => [c.getAttribute("data-key"), c]));
  const keys = new Set(model.pins.map((p) => p.key));
  for (const [k, el] of have) if (!keys.has(k)) fadeRemove(el);
  for (const p of model.pins) {
    let el = have.get(p.key);
    if (!el) {
      el = svg("g", { class: "pin", "data-key": p.key },
        svg("line", { class: "gap-pin", "data-key": p.key }),
        svg("line", { class: "leader" }),
        svg("text", { class: "label label--attention", "text-anchor": "middle" }));
      gaps.append(el);
      if (animate) enter(el);
    }
    const [x1, y1] = pt(163, p.angle);
    const [x2, y2] = pt(179, p.angle);
    setAttrs(el.children[0], { x1, y1, x2, y2 });
    const [l1x, l1y] = pt(182, p.angle);
    const [l2x, l2y] = pt(p.far ? 206 : 192, p.angle);
    setAttrs(el.children[1], { x1: l1x, y1: l1y, x2: l2x, y2: l2y });
    const [tx, ty] = pt(p.far ? 214 : 200, p.angle);
    setAttrs(el.children[2], { x: tx, y: ty });
    if (el.children[2].textContent !== p.label) el.children[2].textContent = p.label;
  }
}

function renderEdge(root, model, animate) {
  let edge = find(root, "g.edge");
  let call = find(root, "g.callouts");
  if (!model.edge) {
    if (edge && animate && !edge.hasAttribute("data-leaving") && durationMs("--dur-breathe") > 0) {
      // Motion 6: activity ended, so the halo finishes the loop it is in, then the edge goes.
      edge.setAttribute("data-leaving", "");
      const halo = find(edge, "circle.edge-halo");
      const done = () => {
        if (!edge.hasAttribute("data-leaving")) return;
        edge.remove();
        if (call && call.isConnected) call.remove();
      };
      if (halo) halo.addEventListener("animationiteration", done, { once: true });
      else done();
      setTimeout(done, durationMs("--dur-breathe") * 2 + 50); // safety net if the animation never ticks (hidden tab)
      return;
    }
    if (edge && edge.hasAttribute("data-leaving")) return;
    if (edge) edge.remove();
    if (call) call.remove();
    return;
  }
  if (edge && edge.hasAttribute("data-leaving")) edge.removeAttribute("data-leaving"); // activity came back mid-loop
  const e = model.edge;
  if (!edge) {
    edge = svg("g", { class: "edge" },
      svg("circle", { class: "edge-halo", cx: C, cy: C - e.r, r: 16 }),
      svg("circle", { class: "edge-tip", cx: C, cy: C - e.r, r: 4.5 }));
    root.append(edge);
  }
  edge.style.transform = `rotate(${f2(e.angle)}deg)`;
  const tip = find(edge, "circle.edge-tip");
  const have = new Map([...edge.querySelectorAll(":scope > g.edge-agent")].map((g) => [g.getAttribute("data-key"), g]));
  const keys = new Set(e.agents.map((a) => a.key));
  for (const [k, g] of have) if (!keys.has(k)) g.remove();
  for (const a of e.agents) {
    let g = have.get(a.key);
    if (!g) {
      g = svg("g", { class: "edge-agent", "data-key": a.key }, svg("circle", { cx: C, cy: C - e.r }));
      edge.insertBefore(g, tip);
      if (animate) enter(g);
    }
    g.style.transform = `rotate(${f2(-a.off)}deg)`;
    const dot = g.firstElementChild;
    setAttrs(dot, { class: a.recent ? "edge-dot edge-dot--recent" : "edge-dot", r: a.recent ? 5 : 6 });
  }
  // Desktop callouts: absolute coordinates, so they sit outside the rotated group.
  if (!call) {
    call = svg("g", { class: "callouts" });
    root.append(call);
  }
  const left = ((e.angle % 360) + 360) % 360 > 180;
  let prevY = -Infinity;
  const parts = [];
  for (const a of e.agents) {
    const [dx, dy] = pt(e.r, a.angle);
    const [sx, sy] = pt(e.r + 9, a.angle);
    const y = r2(Math.max(dy, prevY + 13));
    prevY = y;
    const elbow = left ? 6 : 394;
    const end = left ? -2 : 402;
    const lx = left ? -8 : 408;
    void dx;
    parts.push({ a, sx, sy, y, elbow, end, lx });
  }
  const sig = JSON.stringify(parts);
  if (call.__sig !== sig) {
    call.__sig = sig;
    call.replaceChildren(...parts.flatMap((p) => [
      svg("polyline", { class: "leader leader--agent", points: `${p.sx},${p.sy} ${p.elbow},${p.y} ${p.end},${p.y}` }),
      svg("text", { class: p.a.recent ? "label label--agent label--muted" : "label label--agent", x: p.lx, y: r2(p.y + 3), "text-anchor": left ? "end" : "start" },
        `${p.a.text} `, svg("tspan", { class: "label--muted" }, p.a.sub)),
    ]));
  }
}

let moving = [];
let born = [];

// Overlay groups that the reconciler never touches: effects (ripples, the latest-event beacon) and the hover highlight.
function overlay(root, cls) {
  let g = find(root, `g.${cls}`);
  if (!g) {
    g = svg("g", { class: cls, "aria-hidden": "true" });
    root.append(g);
  } else if (g !== root.lastElementChild && cls === "hl") root.append(g);
  return g;
}

// A new event lands: a ring of light spreads from its tick.
function ripple(root) {
  // New ticks sit out the sweep until their own grow-in transition has run.
  for (const { el } of born) {
    el.setAttribute("data-fresh", "");
    setTimeout(() => el.removeAttribute("data-fresh"), durationMs("--dur-2") + 400);
  }
  if (!born.length || reduced()) {
    born = [];
    return;
  }
  const fx = overlay(root, "fx");
  for (const { ring, t } of born.slice(-6)) {
    const [x, y] = pt(ring.r, t.angle);
    const c = svg("circle", { class: `ripple ripple--${t.tier}`, cx: x, cy: y, r: 4 });
    fx.append(c);
    setTimeout(() => c.remove(), 1600);
  }
  born = [];
}

// The newest event in the record wears a small beacon just outside its ring.
function beacon(root, model, snapshot) {
  const fx = overlay(root, "fx");
  let b = find(fx, "g.beacon");
  const newest = (snapshot.events || [])[0];
  let at = null;
  if (newest) {
    for (const ring of model.rings) {
      const t = ring.ticks.find((x) => x.id === newest.id);
      if (t) {
        at = { ring, t };
        break;
      }
    }
  }
  if (!at) {
    if (b) b.remove();
    return;
  }
  if (!b) {
    b = svg("g", { class: "beacon" }, svg("circle", { class: "beacon__halo", r: 7 }), svg("circle", { class: "beacon__dot", r: 2.6 }));
    fx.prepend(b);
  }
  const rr = at.ring.r + (at.ring.full ? 7 : 3) + 5;
  const [x, y] = pt(rr, at.t.angle);
  b.style.transform = `translate(${x}px, ${y}px)`;
  b.setAttribute("data-event", newest.id);
}

function settleArcs(root) {
  if (!moving.length) return;
  void root.getBoundingClientRect(); // settle the before-change style so the length change below transitions
  // Applied here, after every style flush of this pass, so the data-still switch cannot leak into the chosen arc.
  const keep = moving.find((m) => m.el.classList.contains("arc--live")) || moving[moving.length - 1];
  for (const m of moving) {
    if (m !== keep) m.el.setAttribute("data-still", "");
    m.el.style.strokeDashoffset = m.off;
  }
  if (moving.length > 1) {
    void root.getBoundingClientRect();
    for (const m of moving) m.el.removeAttribute("data-still");
  }
  moving = [];
}

function render(root, snapshot, opts, animate) {
  moving = [];
  born = [];
  const model = layout(snapshot, opts);
  root.__model = model;
  root.__snapshot = snapshot;
  const cycles = new Set(model.rings.map((r) => String(r.cycle)));
  for (const g of [...root.querySelectorAll(":scope > g.ring")]) if (!cycles.has(g.getAttribute("data-cycle"))) g.remove();
  for (const ring of model.rings) renderRing(root, ring, opts, animate);
  // keep rings in ascending order ahead of the gap and edge groups
  const anchor = find(root, "g.gaps");
  for (const g of [...root.querySelectorAll(":scope > g.ring")]) if (anchor) root.insertBefore(g, anchor);
  renderGaps(root, model, animate);
  if (opts.edge) renderEdge(root, model, animate);
  settleArcs(root);
  ripple(root);
  beacon(root, model, snapshot);
  if (root.__hit) highlight(root, root.__hit.key ? refind(root, root.__hit) : null);
  return model;
}

export function buildRings(svgEl, snapshot, { labels = false, edge = false, now, intro = true } = {}) {
  render(svgEl, snapshot, { labels, edge, now }, false);
  // First paint: the rings grow in from the oldest outwards, each turning into place.
  if (intro && !reduced()) {
    svgEl.classList.add("is-intro");
    setTimeout(() => svgEl.classList.remove("is-intro"), 2600);
  }
  return svgEl;
}

// ---------- inspection: what is under the pointer ----------
const norm = (a) => ((a % 360) + 360) % 360;
const angDist = (a, b) => {
  const d = Math.abs(norm(a) - norm(b));
  return Math.min(d, 360 - d);
};

// Client point -> the thing drawn there: an event tick, a run's arc, a cycle's ring, a waiting pin, or the centre.
export function hitTest(svgEl, clientX, clientY) {
  const model = svgEl.__model;
  const m = svgEl.getScreenCTM && svgEl.getScreenCTM();
  if (!model || !m) return null;
  const p = new DOMPoint(clientX, clientY).matrixTransform(m.inverse());
  const dx = p.x - C;
  const dy = p.y - C;
  const r = Math.hypot(dx, dy);
  const ang = norm((Math.atan2(dx, -dy) * 180) / Math.PI);
  if (model.pins.length && r > R_OUT - 10 && r < R_OUT + 52 && angDist(ang, 0) <= model.sec / 2 + 2) {
    let pin = null;
    let pd = Infinity;
    for (const x of model.pins) {
      const d = angDist(x.angle, ang);
      if (d < pd) {
        pd = d;
        pin = x;
      }
    }
    if (pin) return { kind: "pin", key: `pin|${pin.key}`, pin };
  }
  let best = null;
  for (const ring of model.rings) {
    const band = ring.full ? 14 : 5;
    const d = Math.abs(r - ring.r);
    if (d <= band && (!best || d < best.d)) best = { ring, d };
  }
  if (!best) {
    const inner = model.rings.length ? Math.min(...model.rings.map((x) => x.r)) : 0;
    return r < inner - 8 ? { kind: "centre", key: "centre" } : null;
  }
  const ring = best.ring;
  const tol = Math.max(0.9, (4 / ring.r) * (180 / Math.PI));
  let tick = null;
  let td = Infinity;
  for (const t of ring.ticks) {
    const d = angDist(t.angle, ang);
    if (d < td) {
      td = d;
      tick = t;
    }
  }
  const arc = ring.arcs.find((a) => angDist(a.start + a.len / 2, ang) <= a.len / 2 + ARC_GAP / 2);
  const near = tick && td <= tol ? tick : null;
  if (arc) return { kind: "run", key: `run|${ring.cycle}|${arc.run}|${near ? near.id : ""}`, ring, arc, tick: near };
  if (near) return { kind: "event", key: `event|${near.id}`, ring, tick: near };
  return { kind: "ring", key: `ring|${ring.cycle}`, ring };
}

// After a re-render the model objects are new: find the same thing again by its key.
function refind(svgEl, hit) {
  const model = svgEl.__model;
  if (!model) return null;
  if (hit.kind === "pin") {
    const pin = model.pins.find((x) => `pin|${x.key}` === hit.key);
    return pin ? { ...hit, pin } : null;
  }
  const ring = model.rings.find((x) => x.cycle === (hit.ring && hit.ring.cycle));
  if (!ring) return null;
  if (hit.kind === "event") {
    const tick = ring.ticks.find((t) => t.id === hit.tick.id);
    return tick ? { ...hit, ring, tick, arc: ring.arcs.find((a) => a.events.some((e) => e.id === tick.id)) } : null;
  }
  if (hit.kind === "run") {
    const arc = ring.arcs.find((a) => a.run === hit.arc.run);
    const tick = hit.tick ? ring.ticks.find((t) => t.id === hit.tick.id) || null : null;
    return arc ? { ...hit, ring, arc, tick } : null;
  }
  return hit.kind === "ring" ? { ...hit, ring } : hit;
}

// Draw the hovered thing bright, and let the rest of the picture step back.
export function highlight(svgEl, hit) {
  svgEl.__hit = hit;
  const g = overlay(svgEl, "hl");
  g.replaceChildren();
  svgEl.classList.toggle("is-inspecting", !!hit && hit.kind !== "centre");
  const focus = hit && hit.ring ? String(hit.ring.cycle) : null;
  for (const ring of svgEl.querySelectorAll(":scope > g.ring")) ring.classList.toggle("is-focus", ring.getAttribute("data-cycle") === focus);
  if (!hit || hit.kind === "centre") return;
  if (hit.kind === "ring") {
    g.append(svg("circle", { class: "hl-ring", cx: C, cy: C, r: hit.ring.r }));
    return;
  }
  if (hit.kind === "pin") {
    const [x, y] = pt(171, hit.pin.angle);
    g.append(svg("circle", { class: "hl-pin", cx: x, cy: y, r: 9 }));
    return;
  }
  const arc = hit.arc;
  if (arc) {
    const path = svg("path", { class: hit.kind === "run" ? "hl-arc" : "hl-arc hl-arc--soft", ...arcAttrs(arc, hit.ring.r) });
    path.style.strokeDashoffset = `${f2(360 - arc.len)}px`;
    g.append(path);
  }
  if (hit.tick) {
    const t = hit.tick;
    const [x1, y1] = pt(hit.ring.r - t.len / 2 - 4, t.angle);
    const [x2, y2] = pt(hit.ring.r + t.len / 2 + 4, t.angle);
    g.append(svg("line", { class: `hl-tick hl-tick--${t.tier}`, x1, y1, x2, y2 }));
    const [cx, cy] = pt(hit.ring.r + t.len / 2 + 9, t.angle);
    g.append(svg("circle", { class: `hl-cap hl-cap--${t.tier}`, cx, cy, r: 3 }));
  }
}

export function updateRings(svgEl, snapshot, diff, opts = {}) {
  return render(svgEl, snapshot, opts, true);
}

const SYMBOLS = [
  ["g-proposed", [["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 2.5, "stroke-dasharray": "2 5", "stroke-linecap": "round" }]]],
  ["g-ready", [["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 2.5 }]]],
  ["g-in_progress", [
    ["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 2.5, opacity: 0.3 }],
    ["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 5, pathLength: 100, "stroke-dasharray": "38 100", transform: "rotate(-90 20 20)" }]]],
  ["g-completed", [
    ["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 2.5, opacity: 0.3 }],
    ["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 5, pathLength: 100, "stroke-dasharray": "84 100", transform: "rotate(-90 20 20)" }]]],
  ["g-verified", [
    ["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 5 }],
    ["circle", { cx: 20, cy: 20, r: 5, fill: "currentColor" }]]],
  ["g-blocked", [
    ["circle", { cx: 20, cy: 20, r: 15, fill: "none", stroke: "currentColor", "stroke-width": 5 }],
    ["line", { x1: 8, y1: 8, x2: 32, y2: 32, stroke: "var(--bg)", "stroke-width": 5 }],
    ["line", { x1: 12, y1: 12, x2: 28, y2: 28, stroke: "currentColor", "stroke-width": 2.5 }]]],
];

export function glyphDefs() {
  return svg("svg", { width: 0, height: 0, style: "position:absolute", "aria-hidden": "true", focusable: "false" },
    SYMBOLS.map(([id, shapes]) => svg("symbol", { id, viewBox: "0 0 40 40" }, shapes.map(([tag, attrs]) => svg(tag, attrs)))));
}

export function glyph(status) {
  return svg("svg", { class: `glyph glyph--${status}`, "aria-hidden": "true", focusable: "false" }, svg("use", { href: `#g-${status}` }));
}
