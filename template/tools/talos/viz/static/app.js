// app.js: the shell (ADR-0005 point 1): header, nav, view container, snapshot store with diffs, SSE client, URL contract.
// Every DOM node is built through dom.js. Views never touch the network.
import { h, svg, text } from "./dom.js";
import * as motion from "./motion.js";
import { glyphDefs } from "./rings.js";
import * as nowView from "./views/now.js";
import * as timelineView from "./views/timeline.js";
import * as workView from "./views/work.js";

const params = new URLSearchParams(location.search);
if (params.get("motion") === "reduce") document.documentElement.dataset.motion = "reduce";
const dataName = params.get("data");
const forcedFresh = params.get("fresh");
// ?p=<id> picks one of the projects the server offers (/api/projects); absent means the one it was started on.
const projectId = params.get("p");
const projectQuery = projectId ? `?p=${encodeURIComponent(projectId)}` : "";

const store = { snapshot: null, version: 0, receivedAt: 0 };
const link = { state: "fresh", lostAt: null, lastRead: null };

// ---------- formatting ----------
const pad = (n) => String(n).padStart(2, "0");

function nowMs() {
  const s = store.snapshot;
  if (!s) return Date.now();
  const base = Date.parse(s.generated_at);
  return dataName ? base : base + (Date.now() - store.receivedAt);
}

const fmt = {
  ago(iso) {
    const s = Math.max(0, Math.round((nowMs() - Date.parse(iso)) / 1000));
    if (s < 60) return `${s} s ago`;
    if (s < 3600) return `${Math.floor(s / 60)} min ${s % 60} s ago`;
    return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min ago`;
  },
  clock(iso) {
    return typeof iso === "string" && iso.length >= 19 ? iso.slice(11, 19) : "";
  },
  hm(minutes) {
    const m = Math.max(0, Math.round(Number(minutes) || 0));
    return `${Math.floor(m / 60)}h${pad(m % 60)}m`;
  },
  millions(n) {
    return ((Number(n) || 0) / 1e6).toFixed(2);
  },
  usd(n) {
    return `$${(Number(n) || 0).toFixed(2)}`;
  },
};

// ---------- diff (ADR-0005 amendment) ----------
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export function diffSnapshots(prev, next) {
  const prevEvents = new Set(prev.events.map((e) => e.id));
  const prevWait = new Set(prev.waiting.map((w) => w.key));
  const nextWait = new Set(next.waiting.map((w) => w.key));
  const prevItems = new Map(prev.items.map((i) => [i.id, i]));
  const nextItems = new Map(next.items.map((i) => [i.id, i]));
  const items = { added: [], removed: [], moved: [], changed: [] };
  for (const [id, item] of nextItems) {
    const old = prevItems.get(id);
    if (!old) items.added.push(id);
    else if (old.status !== item.status) items.moved.push({ id, from: old.status, to: item.status });
    else if (!same(old, item)) items.changed.push(id);
  }
  for (const id of prevItems.keys()) if (!nextItems.has(id)) items.removed.push(id);
  return {
    events: { added: next.events.filter((e) => !prevEvents.has(e.id)).map((e) => e.id) },
    waiting: {
      added: next.waiting.filter((w) => !prevWait.has(w.key)).map((w) => w.key),
      removed: prev.waiting.filter((w) => !nextWait.has(w.key)).map((w) => w.key),
    },
    items,
    counts: !same(prev.counts, next.counts),
    cycle: !same(prev.cycle, next.cycle),
    activity: !same(prev.activity, next.activity),
    spend: !same(prev.spend, next.spend),
    report: !same(prev.report, next.report),
    charter: !same(prev.charter, next.charter),
  };
}

// ---------- context handed to views ----------
const ctx = {
  params,
  setParam(name, value) {
    if (value === null || value === undefined) params.delete(name);
    else params.set(name, value);
    history.replaceState(history.state, "", `${location.pathname}?${params}${location.hash}`);
  },
  h,
  svg,
  text,
  motion,
  now: nowMs,
  diff: null,
  fmt,
};

const VIEWS = [nowView, timelineView, workView];
const views = new Map(VIEWS.map((mod) => [mod.id, { id: mod.id, mod, section: null, mounted: false, prev: null, scroll: 0 }]));
const refs = {};
let current = "now";

function viewHref(id) {
  const p = new URLSearchParams();
  p.set("view", id);
  for (const k of ["p", "data", "motion", "fresh"]) if (params.has(k)) p.set(k, params.get(k));
  return `?${p}`;
}

function updateView(v, snapshot) {
  ctx.diff = v.prev ? diffSnapshots(v.prev, snapshot) : null;
  v.mod.update(v.section, snapshot, ctx);
  v.prev = snapshot;
}

function ensureMounted(v) {
  if (!v.mounted) {
    v.mod.mount(v.section, ctx);
    v.mounted = true;
  }
  if (v.prev !== store.snapshot) updateView(v, store.snapshot);
}

// ---------- chrome: header, nav, freshness ----------
// Q-0005, Q-0006: lastRead is the newest checked_at seen on a snapshot or an SSE hello | change | ping.
function noteRead(iso) {
  const t = typeof iso === "string" ? Date.parse(iso) : NaN;
  const at = Number.isFinite(t) ? t : Date.now();
  if (link.lastRead === null || at > link.lastRead) link.lastRead = at;
}

function noteReadFromEvent(ev) {
  let iso = null;
  try {
    iso = JSON.parse(ev.data).checked_at;
  } catch {
    iso = null;
  }
  noteRead(iso);
}

function freshText() {
  const s = store.snapshot;
  const unreadable = `record unreadable since ${fmt.clock(s.generated_at)}`;
  if (dataName) {
    if (forcedFresh === "error") return ["error", unreadable];
    if (forcedFresh === "stale") return ["stale", "record read 42 s ago, retrying"];
    return ["fresh", `fixture ${dataName}`];
  }
  const blocked = (s.errors || []).some((e) => e && (e.block === "ledger" || e.block === "state"));
  if (link.state === "error" || blocked) return ["error", unreadable];
  const n = Math.max(0, Math.floor((Date.now() - (link.lastRead ?? Date.now())) / 1000));
  const stale = n > 30 || (link.lostAt !== null && Date.now() - link.lostAt > 30000);
  return stale ? ["stale", `record read ${n} s ago, retrying`] : ["fresh", `record read ${n} s ago`];
}

function renderFresh() {
  if (!refs.fresh || !store.snapshot) return;
  const [state, label] = freshText();
  if (refs.fresh.getAttribute("data-fresh") !== state) refs.fresh.setAttribute("data-fresh", state);
  if (refs.freshText.textContent === label) return;
  if (refs.freshRendered) motion.tick(refs.freshText, label);
  else refs.freshText.textContent = label;
  refs.freshRendered = true;
}

function renderChrome(snapshot) {
  const name = snapshot.project && snapshot.project.name ? snapshot.project.name : "";
  if (refs.name.textContent !== name) refs.name.textContent = name;
  const rec = snapshot.project && snapshot.project.record ? snapshot.project.record : "";
  if (refs.path.textContent !== rec) refs.path.textContent = rec;
  const n = snapshot.waiting.length;
  refs.count.hidden = n === 0;
  refs.count.setAttribute("aria-label", `${n} waiting on you`);
  motion.tick(refs.count, n);
  renderFresh();
}

// Line icons for the rail, 24-unit grid, drawn with currentColor.
const ICONS = {
  now: [["circle", { cx: 12, cy: 12, r: 9 }], ["circle", { cx: 12, cy: 12, r: 5 }], ["circle", { cx: 12, cy: 3, r: 1.6, class: "ico-fill" }]],
  timeline: [["path", { d: "M6 4v16" }], ["circle", { cx: 6, cy: 7, r: 1.6, class: "ico-fill" }], ["circle", { cx: 6, cy: 13, r: 1.6, class: "ico-fill" }],
    ["path", { d: "M10 7h9M10 13h6M10 19h8" }]],
  work: [["rect", { x: 3.5, y: 4, width: 4.5, height: 16, rx: 1.2 }], ["rect", { x: 9.75, y: 4, width: 4.5, height: 10, rx: 1.2 }], ["rect", { x: 16, y: 4, width: 4.5, height: 13, rx: 1.2 }]],
  rail: [["rect", { x: 3.5, y: 4.5, width: 17, height: 15, rx: 2.5 }], ["path", { d: "M9.5 4.5v15" }], ["path", { class: "ico-chev", d: "M13.5 9.5 16 12l-2.5 2.5" }]],
};

function icon(name) {
  return svg("svg", { class: `ico ico--${name}`, viewBox: "0 0 24 24", "aria-hidden": "true", focusable: "false" },
    ICONS[name].map(([tag, attrs]) => svg(tag, attrs)));
}

// The mark: three growth rings, each open at a different angle, and the growth-edge dot. Hover sets them turning.
function logo() {
  const arc = (r, gap, cls) => svg("circle", { class: `logo__ring ${cls}`, cx: 16, cy: 16, r, pathLength: 100, "stroke-dasharray": `${100 - gap} ${gap}` });
  return svg("svg", { class: "logo", viewBox: "0 0 32 32", "aria-hidden": "true", focusable: "false" },
    arc(13, 22, "logo__ring--1"), arc(8.5, 30, "logo__ring--2"), arc(4, 40, "logo__ring--3"),
    svg("g", { class: "logo__orbit" }, svg("circle", { class: "logo__dot", cx: 16, cy: 3, r: 2.4 })));
}

function readRail() {
  try {
    return localStorage.getItem("viz.rail") === "open";
  } catch {
    return false;
  }
}

function setRail(open) {
  refs.app.dataset.rail = open ? "open" : "closed";
  refs.railBtn.setAttribute("aria-expanded", String(open));
  refs.railBtn.setAttribute("aria-label", open ? "Collapse sidebar" : "Expand sidebar");
  try {
    localStorage.setItem("viz.rail", open ? "open" : "closed");
  } catch {
    /* private mode: the rail still works for this visit */
  }
}

// ---------- project switcher ----------
function agoSeconds(epoch) {
  if (!epoch) return "no events";
  const s = Math.max(0, Math.round(Date.now() / 1000 - epoch));
  if (s < 90) return "active just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 172800) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

function buildSwitcher() {
  const btn = h("button", { type: "button", class: "top__project switch", "aria-haspopup": "true", "aria-expanded": "false", title: "Switch project" },
    refs.name, " ", refs.path, svg("svg", { class: "switch__chev", viewBox: "0 0 12 12", "aria-hidden": "true", focusable: "false" }, svg("path", { d: "M3 4.5 6 7.5 9 4.5" })));
  const list = h("ul", { class: "switcher__list" });
  const pop = h("div", { class: "switcher", role: "dialog", "aria-label": "Projects", hidden: true },
    h("p", { class: "switcher__h" }, "Talos projects"), list,
    h("p", { class: "switcher__note" }, "Projects with a company/ record, found next to the one this server started on."));
  const wrap = h("div", { class: "top__switch" }, btn, pop);
  let open = false;
  const close = () => {
    if (!open) return;
    open = false;
    btn.setAttribute("aria-expanded", "false");
    pop.classList.remove("is-open");
    setTimeout(() => { if (!open) pop.hidden = true; }, motion.durationMs("--dur-2"));
  };
  const render = (projects) => {
    const here = projectId || (projects.find((p) => p.primary) || {}).id;
    list.replaceChildren(...projects.map((p, i) => {
      const q = new URLSearchParams();
      q.set("p", p.id);
      q.set("view", current);
      const a = h("a", { class: `switcher__item${p.id === here ? " is-current" : ""}`, href: `?${q}`, "aria-current": p.id === here ? "true" : null },
        h("span", { class: "switcher__mark", "aria-hidden": "true" }),
        h("span", { class: "switcher__text" }, h("b", {}, p.name), h("code", {}, p.path)),
        h("span", { class: "switcher__when" }, agoSeconds(p.last_write)));
      a.style.setProperty("--n", String(i));
      a.addEventListener("click", (e) => {
        if (p.id === here) {
          e.preventDefault();
          close();
          return;
        }
        if (e.metaKey || e.ctrlKey || e.shiftKey || motion.reduced()) return;
        e.preventDefault();
        document.body.classList.add("is-switching");
        setTimeout(() => location.assign(a.href), 220);
      });
      return h("li", {}, a);
    }));
  };
  btn.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (open) return close();
    open = true;
    btn.setAttribute("aria-expanded", "true");
    pop.hidden = false;
    requestAnimationFrame(() => pop.classList.add("is-open"));
    if (!list.children.length) list.replaceChildren(h("li", { class: "switcher__loading" }, "Looking for projects…"));
    try {
      const res = await fetch("/api/projects", { cache: "no-store" });
      render((await res.json()).projects || []);
    } catch {
      list.replaceChildren(h("li", { class: "switcher__loading" }, "Could not list projects."));
    }
  });
  document.addEventListener("click", (e) => { if (open && !wrap.contains(e.target)) close(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  return wrap;
}

function buildChrome(snapshot) {
  refs.name = h("span", { class: "top__name" });
  refs.path = h("code", { class: "top__path" });
  refs.freshText = h("span", { class: "top__fresh-text" });
  refs.fresh = h("p", { class: "top__fresh", "data-fresh": "fresh" }, h("span", { class: "dot", "aria-hidden": "true" }), refs.freshText);
  refs.count = h("span", { class: "nav__count" });
  refs.links = new Map();
  const nav = h("nav", { class: "nav", "aria-label": "Views" },
    VIEWS.map((mod) => {
      const a = h("a", { href: viewHref(mod.id), "data-view": mod.id, title: mod.title, "aria-current": mod.id === current ? "page" : null },
        h("span", { class: "nav__icon" }, icon(mod.id)), h("span", { class: "nav__label" }, mod.title), mod.id === "now" ? refs.count : null);
      refs.links.set(mod.id, a);
      return a;
    }));
  refs.railBtn = h("button", { type: "button", class: "rail__toggle", "aria-controls": "rail" }, icon("rail"), h("span", { class: "nav__label" }, "Collapse"));
  refs.railBtn.addEventListener("click", () => setRail(refs.app.dataset.rail !== "open"));
  const rail = h("aside", { class: "rail", id: "rail" }, nav, refs.railBtn);
  const main = h("main", { id: "main", class: "main", tabindex: "-1" });
  for (const v of views.values()) {
    v.section = h("section", { "data-view": v.id, hidden: v.id !== current });
    main.append(v.section);
  }
  const brand = h("a", { class: "brand", href: viewHref("now"), "aria-label": "Talos, Now view" }, logo(), h("span", { class: "brand__word" }, "Talos"));
  const project = buildSwitcher();
  refs.app = h("div", { class: `app app--${current}` },
    h("a", { class: "skip", href: "#main" }, "Skip to content"),
    h("header", { class: "top" }, brand, h("span", { class: "top__rule", "aria-hidden": "true" }), project, refs.fresh),
    rail, main);
  setRail(readRail());
  return refs.app;
}

function setCurrentChrome(id) {
  for (const [vid, a] of refs.links) {
    if (vid === id) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  refs.app.className = `app app--${id}`;
  const mod = views.get(id).mod;
  document.title = `${mod.title} · ${store.snapshot.project.name || "Talos"}`;
}

// ---------- store ----------
function ingest(next) {
  const first = store.snapshot === null;
  store.snapshot = next;
  store.version = next.version ?? store.version;
  store.receivedAt = Date.now();
  noteRead(next.activity && next.activity.checked_at);
  if (first) return;
  renderChrome(next);
  for (const v of views.values()) if (v.mounted) updateView(v, next);
}

async function fetchSnapshot() {
  const url = dataName ? `/static/fixtures/${encodeURIComponent(dataName)}.json` : `/api/snapshot${projectQuery}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

async function refetch() {
  try {
    const next = await fetchSnapshot();
    if (store.snapshot && next.version < store.version) return;
    link.state = "fresh";
    link.lostAt = null;
    ingest(next);
  } catch {
    link.state = "error";
    renderFresh();
  }
}

// The browser drops an EventSource when the machine sleeps or the tab is frozen, and does not always reopen it.
// Pings arrive every 15 s, so a stream silent for 40 s is replaced, and a tab coming back checks at once.
const STREAM_SILENT_MS = 40000;

function connect() {
  if (typeof EventSource !== "function") {
    setInterval(refetch, 10000);
    setInterval(renderFresh, 1000);
    return;
  }
  let es = null;
  let heardAt = Date.now();
  const versionOf = (ev) => {
    try {
      return Number(JSON.parse(ev.data).version);
    } catch {
      return NaN;
    }
  };
  const open = () => {
    if (es) es.close();
    heardAt = Date.now();
    es = new EventSource(`/api/events${projectQuery}`);
    es.addEventListener("hello", (ev) => {
      heardAt = Date.now();
      link.state = "fresh";
      link.lostAt = null;
      noteReadFromEvent(ev);
      renderFresh();
      if (versionOf(ev) !== store.version) refetch();
    });
    es.addEventListener("change", (ev) => {
      heardAt = Date.now();
      noteReadFromEvent(ev);
      const v = versionOf(ev);
      if (!(v <= store.version)) refetch();
    });
    es.addEventListener("ping", (ev) => {
      heardAt = Date.now();
      noteReadFromEvent(ev);
      renderFresh();
    });
    es.onerror = () => {
      if (link.lostAt === null) link.lostAt = Date.now();
    };
  };
  const check = (force) => {
    const silent = Date.now() - heardAt;
    if (es.readyState === EventSource.CLOSED || silent > STREAM_SILENT_MS || (force && silent > 20000)) {
      open();
      refetch();
    }
  };
  open();
  setInterval(renderFresh, 1000);
  setInterval(() => check(false), 5000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") check(true);
  });
  window.addEventListener("online", () => check(true));
  window.addEventListener("pageshow", (e) => {
    if (e.persisted) check(true);
  });
}

// ---------- navigation ----------
function pageUrl(hash) {
  return `${location.pathname}?${params}${hash || ""}`;
}

async function show(id, { push = false, hash = "" } = {}) {
  const v = views.get(id) || views.get("now");
  views.get(current).scroll = window.scrollY;
  ensureMounted(v);
  const from = views.get(current).section;
  params.set("view", v.id);
  if (push) history.pushState(null, "", pageUrl(hash));
  else history.replaceState(history.state, "", pageUrl(hash));
  current = v.id;
  setCurrentChrome(v.id);
  await motion.switchView(from, v.section);
  let target = null;
  if (hash) {
    try {
      target = document.getElementById(decodeURIComponent(hash.slice(1)));
    } catch {
      target = null; // malformed escape in the hash: fall back to the saved scroll position
    }
  }
  if (target) target.scrollIntoView();
  else window.scrollTo(0, v.scroll);
}

document.addEventListener("click", (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target instanceof Element ? e.target.closest("a[href]") : null;
  if (!a) return;
  const href = a.getAttribute("href");
  if (!href || !href.startsWith("?view=")) return;
  e.preventDefault();
  const u = new URL(href, location.href);
  show(u.searchParams.get("view"), { push: true, hash: u.hash });
});

window.addEventListener("popstate", () => {
  for (const k of [...params.keys()]) params.delete(k);
  for (const [k, val] of new URLSearchParams(location.search)) params.set(k, val);
  const id = params.get("view") || "now";
  if (views.has(id) && id !== current) show(id, { hash: location.hash });
});

// ---------- boot ----------
async function boot() {
  let first;
  try {
    first = await fetchSnapshot();
  } catch {
    document.body.append(h("p", { class: "stub", role: "alert" }, "Record unreadable"));
    return;
  }
  const requested = params.get("view");
  current = views.has(requested) ? requested : "now";
  store.snapshot = first;
  store.version = first.version ?? 0;
  store.receivedAt = Date.now();
  noteRead(first.activity && first.activity.checked_at);
  const app = buildChrome(first);
  renderChrome(first);
  setCurrentChrome(current);
  ensureMounted(views.get(current));
  document.body.append(glyphDefs(), app);
  if (dataName) {
    window.__viz = {
      get snapshot() {
        return store.snapshot;
      },
      push(next) {
        ingest(next);
      },
    };
  } else {
    connect();
  }
}

boot();
