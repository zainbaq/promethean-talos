// Canopy view: the company as a tree. Roots are the CEO, the trunk is orchestration, boughs are executives, twigs are
// the roles under them, leaves are single dispatches. Lenses: Tree, Follow (one item's route), Relay (the same route as
// lanes over time). The layout is computed from the whole record, so scrubbing only shows and hides what exists at a time.
export const id = "canopy";
export const title = "Canopy";

const RELOAD_MS = 30000;
const REPLAY_MS = 12000;

const ROLE = {
  ceo: "You", "chief-of-staff": "Chief of Staff", coordinator: "Coordinator", "head-of-product": "Head of Product",
  "chief-architect": "Chief Architect", "head-of-design": "Head of Design", "head-of-qa": "Head of QA",
  "head-of-research": "Head of Research", "learning-officer": "Learning Officer", engineer: "Engineer",
  "devops-engineer": "DevOps Engineer", "technical-writer": "Technical Writer", "test-engineer": "Test Engineer",
  "ui-engineer": "UI Engineer", "ux-designer": "UX Designer", "design-qa": "Design QA", "code-reviewer": "Code Reviewer",
  "security-reviewer": "Security Reviewer", librarian: "Librarian", "research-analyst": "Research Analyst",
};
const roleName = (r) => ROLE[r] || r;

// The org chart. Transcripts name the session that dispatched a task, and that session acts for the department head.
const TREE = [
  { role: "head-of-product", side: -1, at: 0.2, ang: 12, len: 0.3, twigs: [] },
  { role: "chief-architect", side: 1, at: 0.26, ang: 12, len: 0.36, twigs: [
    { role: "engineer", t: 0.72, turn: 40, len: 0.17 }, { role: "devops-engineer", t: 0.42, turn: -24, len: 0.12 },
    { role: "technical-writer", t: 0.95, turn: -18, len: 0.1 }] },
  { role: "head-of-design", side: -1, at: 0.5, ang: 22, len: 0.31, twigs: [
    { role: "ui-engineer", t: 0.55, turn: 38, len: 0.22 }, { role: "design-qa", t: 0.92, turn: 48, len: 0.1 },
    { role: "ux-designer", t: 0.3, turn: -24, len: 0.12 }] },
  { role: "head-of-qa", side: 1, at: 0.58, ang: 26, len: 0.32, twigs: [
    { role: "code-reviewer", t: 0.5, turn: 44, len: 0.16 }, { role: "security-reviewer", t: 0.9, turn: 14, len: 0.14 },
    { role: "test-engineer", t: 0.3, turn: -26, len: 0.13 }] },
  { role: "head-of-research", side: -1, at: 0.74, ang: 42, len: 0.2, twigs: [{ role: "research-analyst", t: 0.7, turn: 36, len: 0.1 }] },
  { role: "learning-officer", side: 1, at: 0.84, ang: 56, len: 0.2, twigs: [{ role: "librarian", t: 0.75, turn: 40, len: 0.09 }] },
];
const CROWN = "chief-of-staff";

const LEAF_WORD = {
  verified: "verified", sent_back: "sent back, then fixed", blocked: "blocked", abandoned: "abandoned",
  open: "not verified yet", support: "planning, review or record",
};
const STATE_WORD = { shipped: "shipped", verified: "verified", blocked: "blocked", open: "in progress" };

const R = new WeakMap();

const M = (n) => (n >= 1e7 ? `${Math.round(n / 1e6)}M` : n >= 1e5 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(n || 0));
const clock = (ts) => (ts || "").slice(11, 16);
const dayClock = (ts) => (ts || "").replace("T", " ").slice(5, 16);
const secs = (ts) => Date.parse(`${(ts || "").slice(0, 19)}Z`);

function span(s) {
  const m = Math.round(s / 60);
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h${String(m % 60).padStart(2, "0")}m`;
}

function bez(c, t) {
  const [p0, c1, c2, p1] = [c.p0, c.c1, c.c2, c.p1];
  const u = 1 - t;
  const a = u * u * u, b = 3 * u * u * t, d = 3 * u * t * t, e = t * t * t;
  const dx = 3 * u * u * (c1[0] - p0[0]) + 6 * u * t * (c2[0] - c1[0]) + 3 * t * t * (p1[0] - c2[0]);
  const dy = 3 * u * u * (c1[1] - p0[1]) + 6 * u * t * (c2[1] - c1[1]) + 3 * t * t * (p1[1] - c2[1]);
  return { x: a * p0[0] + b * c1[0] + d * c2[0] + e * p1[0], y: a * p0[1] + b * c1[1] + d * c2[1] + e * p1[1], a: Math.atan2(dy, dx) };
}

function curve(p0, deg, len, bend) {
  const r = (deg * Math.PI) / 180;
  const cos = Math.cos(r), sin = Math.sin(r);
  const p1 = [p0[0] + cos * len, p0[1] - sin * len];
  const c1 = [p0[0] + cos * len * 0.35, p0[1] - sin * len * 0.35 + bend * len * 0.18];
  const c2 = [p0[0] + cos * len * 0.72, p0[1] - sin * len * 0.72 - bend * len * 0.1];
  return { p0, c1, c2, p1, d: `M${p0}C${c1} ${c2} ${p1}` };
}

function spline(pts) {
  let d = `M${pts[0]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i - 1] || pts[i], b = pts[i], c = pts[i + 1], e = pts[i + 2] || c;
    d += `C${b[0] + (c[0] - a[0]) / 6},${b[1] + (c[1] - a[1]) / 6} ${c[0] - (e[0] - b[0]) / 6},${c[1] - (e[1] - b[1]) / 6} ${c}`;
  }
  return d;
}

// ---------- data helpers ----------
function index(data) {
  const byRole = new Map();
  for (const t of data.tasks) {
    if (!byRole.has(t.role)) byRole.set(t.role, []);
    byRole.get(t.role).push(t);
  }
  const placed = new Set([CROWN]);
  for (const b of TREE) {
    placed.add(b.role);
    for (const w of b.twigs) placed.add(w.role);
  }
  const crown = [...byRole.keys()].filter((r) => !placed.has(r)).flatMap((r) => byRole.get(r));
  return { byRole, crown };
}

function roleTokens(r, role) {
  return (r.ix.byRole.get(role) || []).reduce((s, t) => s + t.tokens, 0);
}

function modelOf(tasks) {
  const n = new Map();
  for (const t of tasks) if (t.model) n.set(t.model, (n.get(t.model) || 0) + 1);
  return [...n.entries()].sort((a, b) => b[1] - a[1]).map(([m]) => m).join(", ");
}

function defaultItem(data) {
  const ids = Object.keys(data.items).sort();
  return ids.filter((i) => data.items[i].steps.some((s) => s.kind === "task")).pop() || ids.pop() || null;
}

// ---------- mount ----------
export function mount(root, ctx) {
  const { h, svg } = ctx;
  const params = ctx.params;
  const r = {
    root, data: null, ix: null, sig: null, lens: params.get("lens") || "tree", item: params.get("item"), pinned: null,
    at: null, playing: null, loadedAt: 0, lastEvent: null, snapshot: null, active: new Set(),
  };
  R.set(root, r);
  r.follow = (item) => follow(r, ctx, item);

  r.lensBtns = ["tree", "follow", "relay"].map((l) => {
    const b = h("button", { type: "button", "data-lens": l }, l[0].toUpperCase() + l.slice(1));
    b.addEventListener("click", () => setLens(r, ctx, l));
    return b;
  });
  r.picker = h("select", { class: "canopy__picker", "aria-label": "Item to follow" });
  r.picker.addEventListener("change", () => follow(r, ctx, r.picker.value));
  r.note = h("p", { class: "canopy__note", hidden: true });
  r.svg = svg("svg", { role: "img", "aria-label": "The company as a tree" });
  r.relay = h("div", { class: "canopy__relay", hidden: true });
  r.empty = h("p", { class: "canopy__empty", hidden: true });
  const swatch = (cls, curled) => svg("svg", { viewBox: "0 0 14 10", "aria-hidden": "true" },
    svg("path", { class: `leaf ${cls}`, d: curled ? "M1 5Q7 -1 13 5Q6 8 1 5" : "M1 5Q7 -1 13 5Q7 11 1 5" }));
  r.legend = h("div", { class: "canopy__legend" },
    h("span", {}, swatch("leaf--verified"), "verified"), h("span", {}, swatch("leaf--sent_back", true), "sent back"),
    h("span", {}, swatch("leaf--support"), "planning, review"), h("span", {}, swatch("leaf--blocked"), "blocked"));
  r.stage = h("section", { class: "canopy__stage" },
    h("div", { class: "canopy__head" }, h("h1", {}, "Canopy"), h("span", { class: "seg", role: "group", "aria-label": "Lens" }, r.lensBtns), r.picker, r.note),
    r.svg, r.relay, r.empty, r.legend);

  r.play = h("button", { type: "button", class: "canopy__play", "aria-label": "Replay the project" },
    svg("svg", { viewBox: "0 0 12 12", "aria-hidden": "true" }, svg("path", { d: "M3 1l7 5-7 5z" })));
  r.play.addEventListener("click", () => replay(r));
  r.range = h("input", { type: "range", class: "canopy__range", min: 0, max: 1000, value: 1000, "aria-label": "Time" });
  r.range.addEventListener("input", () => {
    stopReplay(r);
    setTime(r, Number(r.range.value));
  });
  r.marks = h("div", { class: "canopy__marks", "aria-hidden": "true" });
  r.time = h("time", { class: "canopy__time" });
  r.scrub = h("div", { class: "canopy__scrub" }, r.play, h("div", { class: "canopy__track" }, r.range, r.marks), r.time);

  r.card = h("aside", { class: "canopy__card", "aria-live": "polite" });
  root.append(h("div", { class: "canopy" }, r.stage, r.scrub, r.card));

  r.svg.addEventListener("click", (e) => {
    const hit = e.target instanceof Element ? e.target.closest("[data-task],[data-role],[data-ceo]") : null;
    if (!hit) {
      r.pinned = null;
      drawCard(r, ctx);
      return;
    }
    if (hit.dataset.task) {
      const t = r.data.tasks.find((x) => x.id === hit.dataset.task);
      r.pinned = { task: t };
      if (r.lens === "follow" && t && t.items.length) return follow(r, ctx, t.items[0]);
    } else if (hit.dataset.role) {
      r.pinned = { role: hit.dataset.role };
    } else {
      r.pinned = { ceo: Number(hit.dataset.ceo) };
    }
    markPinned(r);
    drawCard(r, ctx);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && r.pinned) {
      r.pinned = null;
      markPinned(r);
      drawCard(r, ctx);
    }
  });
  new ResizeObserver(() => {
    if (r.data && !root.hidden) draw(r, ctx);
  }).observe(r.stage);
}

export function update(root, snapshot, ctx) {
  const r = R.get(root);
  r.snapshot = snapshot;
  r.active = new Set((snapshot.activity && snapshot.activity.agents || []).filter((a) => a.state === "active").map((a) => a.role));
  const newest = snapshot.events[0] ? snapshot.events[0].id : null;
  const stale = Date.now() - r.loadedAt > RELOAD_MS;
  const live = `${[...r.active].sort()}|${snapshot.waiting.length}`;
  if (r.data === null || newest !== r.lastEvent || (r.active.size && stale)) {
    r.lastEvent = newest;
    r.live = live;
    load(r, ctx);
  } else if (live !== r.live) { // redrawing restarts the pulses, so only when something on the picture changed
    r.live = live;
    draw(r, ctx);
  }
}

async function load(r, ctx) {
  r.loadedAt = Date.now();
  try {
    const data = await ctx.hierarchy();
    const sig = JSON.stringify(data);
    r.failed = false;
    if (sig === r.sig) return;
    r.sig = sig;
    r.data = data;
    r.ix = index(data);
    if (!r.item || !data.items[r.item]) r.item = defaultItem(data);
  } catch {
    r.failed = true;
    if (r.data === null) r.data = { tasks: [], sessions: [], ceo: [], cycles: [], items: {}, totals: {}, source: "none" };
    if (!r.ix) r.ix = index(r.data);
  }
  draw(r, ctx);
}

function setLens(r, ctx, lens) {
  stopReplay(r);
  r.lens = lens;
  ctx.setParam("lens", lens === "tree" ? null : lens);
  r.pinned = null;
  draw(r, ctx);
}

function follow(r, ctx, item) {
  r.item = item;
  ctx.setParam("item", item);
  if (r.lens === "tree") r.lens = "follow";
  ctx.setParam("lens", r.lens);
  draw(r, ctx);
}

// ---------- draw ----------
function draw(r, ctx) {
  if (!r.data) return;
  for (const b of r.lensBtns) b.setAttribute("aria-pressed", String(b.dataset.lens === r.lens));
  const ids = Object.keys(r.data.items).sort();
  r.picker.hidden = r.lens === "tree" || ids.length === 0;
  r.picker.replaceChildren(...ids.map((i) => ctx.h("option", { value: i, selected: i === r.item }, i)));
  r.note.hidden = r.data.source !== "ledger";
  r.note.textContent = r.data.source === "ledger" ? "From the ledger only: no transcripts here, so no per-task cost." : "";
  const none = r.data.tasks.length === 0 && r.data.ceo.length === 0;
  r.empty.hidden = !(none || r.failed);
  r.empty.textContent = r.failed ? "The hierarchy could not be read." : "The tree grows from the first thing you ask for.";
  r.svg.style.display = none || r.lens === "relay" ? "none" : "";
  r.relay.hidden = r.lens !== "relay" || none;
  r.scrub.hidden = r.lens !== "tree" || none;
  r.legend.hidden = r.lens === "relay" || none;
  if (!none && r.lens === "relay") drawRelay(r, ctx);
  else if (!none) drawTree(r, ctx);
  buildScrub(r);
  drawCard(r, ctx);
}

function drawTree(r, ctx) {
  const box = r.stage.getBoundingClientRect();
  if (!box.width || !box.height) return;
  const { svg } = ctx;
  const W = box.width, H = box.height, phone = W < 520, data = r.data, follows = r.lens === "follow";
  const add = (tag, attrs, parent = r.svg) => {
    const e = svg(tag, attrs);
    parent.append(e);
    return e;
  };
  r.svg.replaceChildren();
  r.svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  r.svg.classList.toggle("is-following", follows);
  const S = Math.min(W, H * (phone ? 1.05 : 1.4));
  const cx = W * (phone ? 0.5 : 0.48), ground = H - (phone ? 60 : 92), trunkH = H * (phone ? 0.58 : 0.54), top = ground - trunkH;
  const maxTok = Math.max(1, ...data.tasks.map((t) => t.tokens));
  const times = [];
  const timed = (el, ts) => {
    if (ts) {
      el.dataset.t = ts;
      times.push(el);
    }
    return el;
  };

  // fog: tokens not tied to any item
  const totals = data.totals, share = totals.tokens ? totals.unattributed / totals.tokens : 0;
  const grad = add("radialGradient", { id: "canopy-fog" }, add("defs", {}));
  add("stop", { offset: "0%", "stop-opacity": 0.16 }, grad);
  add("stop", { offset: "100%", "stop-opacity": 0 }, grad);
  grad.setAttribute("class", "tree-fog");
  if (share) {
    add("ellipse", { fill: "url(#canopy-fog)", cx, cy: top + trunkH * 0.55, rx: S * 0.12 + S * 0.25 * share, ry: trunkH * 0.42 });
    if (!phone) add("text", { class: "tree-sub", x: 20, y: ground - 10 }).textContent = `fog · ${Math.round(share * 100)}% of tokens not tied to an item`;
  }

  // roots: the CEO
  add("line", { class: "tree-ground", x1: 16, x2: W - 16, y1: ground, y2: ground });
  data.ceo.forEach((e, i) => {
    const f = (i + 0.5) / data.ceo.length - 0.5;
    const ex = cx + f * S * 0.9, ey = ground + 18 + (1 - Math.abs(f) * 2) * (phone ? 28 : 50);
    timed(add("path", { class: "tree-root dim", "stroke-width": 1.4, d: `M${cx},${ground}C${cx + f * 30},${ground + 30} ${ex},${ey - 30} ${ex},${ey}` }), e.ts);
    timed(add("circle", { class: "tree-tip dim", cx: ex, cy: ey, r: phone ? 4 : 2.8, "data-ceo": i }), e.ts);
  });
  const waiting = r.snapshot ? r.snapshot.waiting.length : 0;
  const decisions = data.ceo.length;
  add("text", { class: "tree-knot-lbl", x: cx, y: H - 8, "text-anchor": "middle" }).textContent =
    `you · ${decisions} decision${decisions === 1 ? "" : "s"}, ${totals.questions || 0} question${totals.questions === 1 ? "" : "s"} asked`;

  // trunk: orchestration, its girth the share of tokens it took
  const orch = totals.tokens ? (totals.orchestration || 0) / totals.tokens : 0;
  const tw = (phone ? 8 : 14) + (phone ? 14 : 32) * Math.sqrt(orch);
  add("path", { class: "tree-trunk dim", "data-role": CROWN,
    d: `M${cx - tw / 2},${ground} C${cx - tw / 3},${top + trunkH * 0.5} ${cx - 4},${top + 30} ${cx - 3},${top} L${cx + 3},${top} C${cx + 4},${top + 30} ${cx + tw / 3},${top + trunkH * 0.5} ${cx + tw / 2},${ground} Z` });
  if (!phone && data.sessions.length) add("text", { class: "tree-sub dim", x: cx + tw / 2 + 8, y: ground - trunkH * 0.12 }).textContent = `trunk · ${data.sessions.length} phase runs, ${M(totals.orchestration)}`;

  // gates, the knots at the base; a gate waiting on you shows in the attention colour
  const gates = [["charter", /^charter\.approved/], ["design", /^design\.approved/], ["plan", /^plan\.approved/], ["release", /^release\.approved/]];
  let knot = 0;
  for (const [name, re] of gates) {
    const hits = data.ceo.filter((e) => re.test(e.event || ""));
    if (!hits.length) continue;
    const y = ground - trunkH * 0.04 - knot * 13;
    timed(add("circle", { class: "tree-knot dim", cx: cx + (knot % 2 ? 1 : -1) * 0.5, cy: y, r: 4.2 }), hits[0].ts);
    if (!phone) add("text", { class: "tree-knot-lbl dim", x: cx - tw / 2 - 8, y: y + 3, "text-anchor": "end" }).textContent = hits.length > 1 ? `${name} ×${hits.length}` : name;
    knot++;
  }
  if (waiting) {
    const y = ground - trunkH * 0.04 - knot * 13;
    add("circle", { class: "tree-knot tree-knot--waiting", cx, cy: y, r: 5 });
    add("text", { class: "tree-attn", x: cx + tw / 2 + 8, y: y + 3 }).textContent = `${waiting} waiting on you`;
  }

  // boughs, twigs and leaves
  const anchors = new Map(), leafSpots = new Map();
  const firstTs = (roles) => roles.flatMap((x) => (r.ix.byRole.get(x) || []).map((t) => t.start)).filter(Boolean).sort()[0];
  for (const b of TREE) {
    const twigs = b.twigs.filter((w) => r.ix.byRole.has(w.role));
    if (!r.ix.byRole.has(b.role) && !twigs.length) continue;
    const dir = b.side > 0 ? b.ang : 180 - b.ang;
    const cv = curve([cx + b.side * 2, ground - trunkH * b.at], dir, S * b.len * (phone ? 0.92 : 1), 1);
    const tok = [b.role, ...twigs.map((w) => w.role)].reduce((s, x) => s + roleTokens(r, x), 0);
    const width = 2 + 7 * Math.sqrt(totals.tokens ? tok / totals.tokens : 0);
    timed(add("path", { class: "tree-bough dim", d: cv.d, "stroke-width": width.toFixed(1), "data-role": b.role }), firstTs([b.role, ...twigs.map((w) => w.role)]));
    anchors.set(b.role, cv);
    for (const w of twigs) {
      const pt = bez(cv, w.t);
      const deg = (-pt.a * 180) / Math.PI + (b.side > 0 ? w.turn : -w.turn);
      const tcv = curve([pt.x, pt.y], deg, S * w.len * (phone ? 0.92 : 1), 0.6);
      const twigW = 1.2 + 3 * Math.sqrt(totals.tokens ? roleTokens(r, w.role) / totals.tokens : 0);
      timed(add("path", { class: "tree-twig dim", d: tcv.d, "stroke-width": twigW.toFixed(1), "data-role": w.role }), firstTs([w.role]));
      anchors.set(w.role, tcv);
    }
  }
  const crown = curve([cx, top + 2], 90, S * 0.09, 0);
  anchors.set(CROWN, crown);
  add("path", { class: "tree-twig dim", d: crown.d, "stroke-width": 2, "data-role": CROWN });

  const leaves = (cv, tasks, startT) => {
    tasks.forEach((t, i) => {
      const tt = startT + ((1 - startT) * (i + 0.6)) / (tasks.length + 0.2);
      const pt = bez(cv, tt);
      const L = (phone ? 7 : 11) + (phone ? 12 : 22) * Math.sqrt(t.tokens / maxTok), w = L * 0.38;
      const ang = (pt.a * 180) / Math.PI + (i % 2 ? 58 : -58);
      const curled = t.outcome === "sent_back";
      const bud = t.outcome === "blocked";
      const fallen = t.outcome === "abandoned";
      const d = bud ? `M${L * 0.2},0a${L * 0.2},${L * 0.2} 0 1 0 ${L * 0.4},0a${L * 0.2},${L * 0.2} 0 1 0 ${-L * 0.4},0`
        : curled ? `M0,0Q${L * 0.5},${-w * 1.3} ${L},0Q${L * 0.42},${w * 0.4} 0,0` : `M0,0Q${L * 0.5},${-w} ${L},0Q${L * 0.5},${w} 0,0`;
      const x = fallen ? cx + ((i % 7) - 3) * 22 + (cv.p1[0] - cx) * 0.4 : pt.x;
      const y = fallen ? ground - 3 : pt.y;
      const rot = fallen ? 8 : ang;
      const leaf = add("path", { class: `leaf leaf--${t.outcome} dim`, d, transform: `translate(${x},${y}) rotate(${rot})`, "data-task": t.id });
      add("title", {}, leaf).textContent = `${t.desc} · ${roleName(t.role)}${t.tokens ? ` · ${M(t.tokens)} tokens` : ""}`;
      timed(leaf, t.start);
      leafSpots.set(t.id, { x: x + (Math.cos((rot * Math.PI) / 180) * L) / 2, y: y + (Math.sin((rot * Math.PI) / 180) * L) / 2, leaf });
    });
  };
  for (const [role, cv] of anchors) {
    const tasks = r.ix.byRole.get(role) || [];
    leaves(cv, role === CROWN ? tasks.concat(r.ix.crown) : tasks, role === CROWN ? 0.2 : 0.28);
  }

  // labels
  const labels = new Map();
  for (const [role, cv] of anchors) {
    const tasks = r.ix.byRole.get(role) || [];
    if (role === CROWN && !tasks.length && !r.ix.crown.length) continue;
    const exec = role === CROWN || TREE.some((b) => b.role === role);
    if (phone && !exec) continue;
    const mid = role === CROWN, right = cv.p1[0] >= cx;
    let x = mid ? cv.p1[0] : cv.p1[0] + (right ? 8 : -8), y = cv.p1[1] - (mid ? 8 : 2);
    let anchor = mid ? "middle" : right ? "start" : "end";
    const wide = Math.max(roleName(role).length, phone ? 0 : 22) * 6.7; // a fixed-width face: wide enough for the sub line too
    if (right && !mid && x + wide > W - 6) {
      x = W - 6;
      anchor = "end";
      y -= 12;
    } else if (!right && !mid && x - wide < 6) {
      x = 6;
      anchor = "start";
      y -= 12;
    }
    const lbl = add("text", { class: "tree-lbl dim", x, y, "text-anchor": anchor, "data-role": role });
    lbl.textContent = roleName(role);
    labels.set(role, lbl);
    if (!phone) add("text", { class: "tree-sub dim", x, y: y + 13, "text-anchor": anchor }).textContent = [`${tasks.length} task${tasks.length === 1 ? "" : "s"}`, tasks.some((t) => t.tokens) ? M(roleTokens(r, role)) : null, modelOf(tasks) || null].filter(Boolean).join(" · ");
  }

  // live: a pulse climbs to each role working right now, and nowhere else
  if (!follows) {
    [...r.active].filter((role) => anchors.has(role)).forEach((role, i) => {
      const cv = anchors.get(role);
      const id = `canopy-live-${i}`;
      add("path", { id, fill: "none", d: `M${cx},${ground}L${cv.p0}${cv.d.replace(/^M[^C]+/, "")}` });
      const dot = add("circle", { class: "tree-pulse", r: 3.5 });
      const m = add("animateMotion", { dur: "3.5s", repeatCount: "indefinite" }, dot);
      add("mpath", { href: `#${id}` }, m);
    });
  }

  // follow: the item's real route, from your words to its last step
  if (follows && r.item && data.items[r.item]) {
    const route = data.items[r.item];
    const pts = [[cx, ground + 34]];
    const seen = [];
    for (const s of route.steps) {
      let at = null;
      if (s.task && leafSpots.has(s.task)) {
        const spot = leafSpots.get(s.task);
        spot.leaf.classList.remove("dim");
        add("circle", { class: "tree-ring", cx: spot.x, cy: spot.y, r: phone ? 9 : 13 });
        at = [spot.x, spot.y];
      } else if (s.actor !== CROWN && s.actor !== "ceo" && anchors.has(s.actor)) {
        const p = bez(anchors.get(s.actor), 0.7);
        at = [p.x, p.y];
      }
      if (labels.has(s.actor)) labels.get(s.actor).classList.remove("dim");
      if (!at) continue; // the Chief of Staff and you are on the trunk, which every hop between branches passes through
      if (seen[seen.length - 1] === s.actor) continue;
      if (seen.length) pts.push([cx, ground - trunkH * (0.2 + 0.08 * seen.length)]);
      seen.push(s.actor);
      pts.push(at);
    }
    if (seen.length) pts.push([cx, ground - trunkH * 0.2]);
    pts.push([cx, ground - 4]);
    if (pts.length > 2) {
      add("path", { class: "tree-route", id: "canopy-route", d: spline(pts) });
      [0, 1.3, 2.6].forEach((begin) => {
        const dot = add("circle", { class: "tree-pulse", r: 4 });
        const m = add("animateMotion", { dur: "4s", repeatCount: "indefinite", begin: `-${begin}s` }, dot);
        add("mpath", { href: "#canopy-route" }, m);
      });
    }
    const wait = longestCeoWait(route);
    if (wait) add("text", { class: "tree-attn", x: cx + tw / 2 + 8, y: ground - 8 }).textContent = `waited ${span(wait)} for you`;
  }
  r.timed = times;
  markPinned(r);
  applyTime(r);
}

function longestCeoWait(route) {
  return route.steps.reduce((best, s) => (s.on_you && s.wait > best ? s.wait : best), 0);
}

function markPinned(r) {
  for (const el of r.svg.querySelectorAll(".leaf.is-pinned")) el.classList.remove("is-pinned");
  const t = r.pinned && r.pinned.task;
  if (t) {
    const el = r.svg.querySelector(`[data-task="${CSS.escape(t.id)}"]`);
    if (el) el.classList.add("is-pinned");
  }
}

// ---------- relay: one lane per role, the baton jumping between them ----------
function drawRelay(r, ctx) {
  const { svg } = ctx;
  const route = r.item && r.data.items[r.item];
  if (!route) return r.relay.replaceChildren();
  const lanes = [];
  for (const s of route.steps) if (!lanes.includes(s.actor)) lanes.push(s.actor);
  const laneH = 44, left = 132, topY = 24;
  let x = left + 8;
  const stops = route.steps.map((s) => {
    x += 44 + (s.wait ? Math.min(150, 14 * Math.log2(1 + s.wait / 60)) : 0);
    return { s, x, y: topY + lanes.indexOf(s.actor) * laneH };
  });
  const W = x + 60, H = topY + lanes.length * laneH + 10;
  const g = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${r.item} handed between roles over time` });
  const add = (tag, attrs) => {
    const e = svg(tag, attrs);
    g.append(e);
    return e;
  };
  lanes.forEach((role, i) => {
    add("line", { class: "lane", x1: left, x2: W, y1: topY + i * laneH, y2: topY + i * laneH });
    add("text", { class: "lane-lbl", x: 12, y: topY + i * laneH + 4 }).textContent = roleName(role);
  });
  stops.forEach((p, i) => {
    const prev = stops[i - 1];
    if (prev) {
      add("path", { class: p.s.on_you ? "baton-wait" : p.s.wait ? "baton baton--gap" : "baton", d: `M${prev.x},${prev.y}C${(prev.x + p.x) / 2},${prev.y} ${(prev.x + p.x) / 2},${p.y} ${p.x},${p.y}` });
      if (p.s.wait >= 1800) add("text", { class: p.s.on_you ? "baton-wait-lbl" : "baton-t", x: (prev.x + p.x) / 2, y: Math.min(prev.y, p.y) - 6, "text-anchor": "middle" }).textContent = span(p.s.wait);
    }
    const dot = add("circle", { class: `baton-stop${p.s.actor === "ceo" ? " baton-stop--ceo" : ""}`, cx: p.x, cy: p.y, r: 5 });
    dot.append(svg("title", {}, `${clock(p.s.ts)} ${roleName(p.s.actor)}: ${p.s.what}`));
    if (i === 0 || p.s.wait >= 1800) add("text", { class: "baton-t", x: p.x, y: p.y + 16, "text-anchor": "middle" }).textContent = clock(p.s.ts);
  });
  r.relay.replaceChildren(g);
}

// ---------- scrubber ----------
function bounds(r) {
  const ts = [...r.data.tasks.map((t) => t.start), ...r.data.ceo.map((e) => e.ts)].filter(Boolean).map(secs).filter(Number.isFinite);
  return ts.length ? [Math.min(...ts), Math.max(...ts)] : null;
}

function buildScrub(r) {
  const b = bounds(r);
  r.bounds = b;
  r.scrub.hidden = r.scrub.hidden || !b;
  if (!b) return;
  const span_ = Math.max(1, b[1] - b[0]);
  r.marks.replaceChildren(...r.data.cycles.map((c) => {
    const el = document.createElement("span");
    el.textContent = `cycle ${c.n}`;
    el.style.left = `${Math.max(0, Math.min(90, ((secs(c.ts) - b[0]) / span_) * 100))}%`;
    return el;
  }));
  applyTime(r);
}

function setTime(r, v) {
  r.range.value = String(v);
  r.at = v >= 1000 ? null : v;
  applyTime(r);
}

function applyTime(r) {
  if (!r.bounds || !r.timed) return;
  const cut = r.at === null ? Infinity : r.bounds[0] + (r.bounds[1] - r.bounds[0]) * (r.at / 1000);
  for (const el of r.timed) el.style.display = secs(el.dataset.t) <= cut ? "" : "none";
  const shown = r.at === null ? r.bounds[1] : cut;
  r.time.textContent = r.at === null ? "now" : new Date(shown).toISOString().slice(5, 16).replace("T", " ");
}

function stopReplay(r) {
  if (r.playing) cancelAnimationFrame(r.playing);
  r.playing = null;
}

function replay(r) {
  stopReplay(r);
  const start = performance.now();
  const step = (t) => {
    const v = Math.min(1000, ((t - start) / REPLAY_MS) * 1000);
    setTime(r, v);
    r.playing = v < 1000 ? requestAnimationFrame(step) : null;
  };
  r.playing = requestAnimationFrame(step);
}

// ---------- the card ----------
function drawCard(r, ctx) {
  const { h } = ctx;
  const p = r.pinned;
  let body;
  if (p && p.task) body = taskCard(r, h, p.task);
  else if (p && p.role) body = roleCard(r, h, p.role);
  else if (p && Number.isInteger(p.ceo) && r.data.ceo[p.ceo]) body = ceoCard(h, r.data.ceo[p.ceo]);
  else if (r.lens !== "tree" && r.item && r.data.items[r.item]) body = itemCard(r, h);
  else body = companyCard(r, h);
  r.card.replaceChildren(...body.flat());
}

const stat = (h, big, small) => h("div", {}, h("b", {}, big), h("span", {}, small));

function companyCard(r, h) {
  const d = r.data, t = d.totals;
  const items = Object.values(d.items);
  const done = items.filter((i) => i.state === "verified" || i.state === "shipped").length;
  const heavy = [...r.ix.byRole.keys()].sort((a, b) => roleTokens(r, b) - roleTokens(r, a)).slice(0, 5);
  return [
    h("p", { class: "canopy__kicker" }, "The whole company"),
    h("h2", {}, r.snapshot ? r.snapshot.project.name : ""),
    h("p", { class: "canopy__meta" }, `${d.tasks.length} dispatched task${d.tasks.length === 1 ? "" : "s"} · ${r.ix.byRole.size} role${r.ix.byRole.size === 1 ? "" : "s"}`),
    h("div", { class: "canopy__stats" },
      stat(h, t.cost_usd ? `$${Math.round(t.cost_usd)}` : "–", "measured"),
      stat(h, `${done}/${items.length}`, "items verified"),
      stat(h, t.tokens ? `${Math.round((t.orchestration / t.tokens) * 100)}%` : "–", "orchestration")),
    h("p", { class: "canopy__kicker" }, "Heaviest branches"),
    h("ol", { class: "relay" }, heavy.map((role) => h("li", {},
      h("div", { class: "relay__who" }, [roleName(role), modelOf(r.ix.byRole.get(role))].filter(Boolean).join(" · ")),
      h("div", { class: "relay__what" }, `${r.ix.byRole.get(role).length} tasks · ${M(roleTokens(r, role))} tokens`)))),
    h("p", { class: "canopy__hint" }, "Tap a branch or leaf for its card. Follow shows one item's path, from your words to its release."),
  ];
}

function itemCard(r, h) {
  const route = r.data.items[r.item];
  const total = route.first && route.last ? (secs(route.last) - secs(route.first)) / 1000 : 0;
  const snapItem = r.snapshot && r.snapshot.items.find((i) => i.id === r.item);
  const rows = [];
  for (const s of route.steps) {
    if (s.wait) {
      rows.push(h("li", { class: s.on_you ? "is-wait" : "" }, s.on_you
        ? h("div", { class: "relay__wait" }, h("b", {}, `Waited ${span(s.wait)}`), " for you")
        : h("div", { class: "relay__gap" }, `${span(s.wait)} gap`)));
    }
    const ok = s.kind === "item.verified" || s.kind === "release.shipped";
    rows.push(h("li", { class: s.actor === "ceo" ? "is-you" : ok ? "is-ok" : "" },
      h("div", { class: "relay__who" }, `${clock(s.ts)} · ${roleName(s.actor)}`),
      h("div", { class: "relay__what" }, s.what, s.tokens ? ` · ${M(s.tokens)} tokens` : "")));
  }
  const rework = route.sent_back;
  return [
    h("p", { class: "canopy__kicker" }, "Following"),
    h("h2", {}, snapItem && snapItem.title ? `${r.item} · ${snapItem.title}` : r.item),
    h("p", { class: "canopy__meta" }, STATE_WORD[route.state] || route.state),
    h("div", { class: "canopy__stats" },
      stat(h, route.tokens ? M(route.tokens) : "–", "tokens"),
      stat(h, String(rework), `sent back`),
      stat(h, span(total), "start to last step")),
    h("ol", { class: "relay" }, rows),
  ];
}

function taskCard(r, h, t) {
  const item = t.items[0];
  let link = null;
  if (item) {
    link = h("a", { href: `?view=canopy&lens=follow&item=${item}` }, `Follow ${item}`);
    link.addEventListener("click", (e) => {
      e.preventDefault();
      r.pinned = null;
      r.follow(item);
    });
  }
  return [
    h("p", { class: "canopy__kicker" }, `Task · ${LEAF_WORD[t.outcome] || t.outcome}`),
    h("h2", {}, t.desc || "(no description)"),
    h("p", { class: "canopy__meta" }, `${t.phase ? `${t.phase} session → ` : ""}${roleName(t.role)}${t.model ? ` · ${t.model}` : ""}`),
    h("div", { class: "canopy__stats" },
      stat(h, t.tokens ? M(t.tokens) : "–", "tokens"),
      stat(h, t.start && t.end ? span((secs(t.end) - secs(t.start)) / 1000) : "–", "ran for"),
      stat(h, clock(t.start) || "–", dayClock(t.start).slice(0, 5))),
    t.branch ? h("p", { class: "canopy__meta" }, h("code", {}, t.branch)) : null,
    link ? h("p", { class: "canopy__hint" }, link) : null,
  ].filter(Boolean);
}

function roleCard(r, h, role) {
  const tasks = r.ix.byRole.get(role) || [];
  const chief = role === CROWN;
  const parent = TREE.find((b) => b.twigs.some((w) => w.role === role));
  const items = new Set(tasks.flatMap((t) => t.items));
  const verified = [...items].filter((i) => r.data.items[i] && ["verified", "shipped"].includes(r.data.items[i].state)).length;
  const events = r.snapshot ? r.snapshot.events.filter((e) => e.actor === role).length : 0;
  return [
    h("p", { class: "canopy__kicker" }, "Role"),
    h("h2", {}, roleName(role)),
    h("p", { class: "canopy__meta" }, chief ? "The trunk: runs each phase and dispatches the others." : parent ? `Under ${roleName(parent.role)}` : "Reports to the Chief of Staff"),
    h("div", { class: "canopy__stats" },
      stat(h, String(tasks.length), "tasks received"),
      stat(h, tasks.some((t) => t.tokens) ? M(roleTokens(r, role)) : "–", "tokens"),
      stat(h, String(verified), "items verified")),
    h("p", { class: "canopy__meta" }, [modelOf(tasks) ? `Model: ${modelOf(tasks)}` : null, `${events} ledger event${events === 1 ? "" : "s"}`].filter(Boolean).join(" · ")),
  ];
}

function ceoCard(h, e) {
  return [
    h("p", { class: "canopy__kicker" }, `You · ${dayClock(e.ts)}`),
    h("h2", {}, e.event || "note"),
    h("p", { class: "canopy__meta" }, e.summary),
    e.ref ? h("p", { class: "canopy__meta" }, h("code", {}, e.ref)) : null,
  ].filter(Boolean);
}
