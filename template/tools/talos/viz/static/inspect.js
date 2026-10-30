// inspect.js: hover and tap on the rings. A card follows the pointer and says what is under it; a tap pins the card.
// The legend under the rings explains the marks, and hovering a legend entry isolates those marks in the picture.
import { hitTest, highlight } from "./rings.js";

const PHASES = {
  kickoff: "Kickoff · the brief becomes a charter",
  plan: "Plan · specs, design and the backlog",
  review: "Review · your decisions recorded",
  cycle: "Cycle · build, verify and close",
  "cycle-build": "Build · engineers work the items",
  "cycle-verify": "Verify · tests, reviews and design QA",
  "cycle-close": "Close · the cycle report",
  retro: "Retro · lessons from the cycle",
  status: "Status",
};
const TIERS = [
  ["ceo", "you"],
  ["executive", "leads"],
  ["execution", "builders"],
  ["review", "reviewers"],
  ["mechanical", "mechanical"],
];

function clockSpan(fmt, a, b) {
  const ms = Date.parse(b) - Date.parse(a);
  const span = Number.isFinite(ms) && ms > 0 ? fmt.hm(ms / 60000) : "";
  return `${fmt.clock(a).slice(0, 5)} to ${fmt.clock(b).slice(0, 5)}${span ? ` · ${span}` : ""}`;
}

function tierBar(h, events) {
  const n = events.length || 1;
  const counts = TIERS.map(([t, word]) => [t, word, events.filter((e) => (e.tier || "execution") === t).length]).filter((x) => x[2]);
  return [
    h("div", { class: "tip__bar", "aria-hidden": "true" }, counts.map(([t, , c]) => h("span", { class: `tip__seg tip__seg--${t}`, style: `flex-grow:${c / n}` }))),
    h("p", { class: "tip__legend" }, counts.map(([t, word, c]) => h("span", {}, h("i", { class: `tip__key tip__key--${t}` }), `${c} ${word}`))),
  ];
}

function topActors(events, k = 3) {
  const by = new Map();
  for (const e of events) by.set(e.actor, (by.get(e.actor) || 0) + 1);
  return [...by].sort((a, b) => b[1] - a[1]).slice(0, k);
}

function eventNodes(h, fmt, e, tick, withCycle) {
  const who = e.tier === "ceo" ? "you" : e.actor;
  return [
    h("p", { class: "tip__kicker" }, `${fmt.clock(e.ts)}${withCycle ? ` · cycle ${e.cycle}${e.phase ? ` · ${e.phase}` : ""}` : ""}`),
    h("p", { class: "tip__title" }, h("code", {}, e.event), e.ref ? [" ", h("span", { class: "tip__ref" }, e.ref)] : null),
    h("p", { class: "tip__who" }, h("i", { class: `tip__key tip__key--${e.tier}` }), who, h("span", { class: "tip__muted" }, ` · ${e.tier}`)),
    e.summary ? h("p", { class: "tip__body" }, e.summary) : null,
    tick.count > 1 ? h("p", { class: "tip__muted" }, `${tick.count} events share this mark; the Timeline lists each.`) : null,
  ];
}

function cardFor(hit, snap, ctx) {
  const { h, fmt } = ctx;
  const byId = new Map((snap.events || []).map((e) => [e.id, e]));
  const ev = hit.tick ? byId.get(hit.tick.id) : null;
  if (hit.kind === "event") {
    if (!ev) return null;
    return { tier: ev.tier, nodes: eventNodes(h, fmt, ev, hit.tick, true), link: [`?view=timeline#${ev.id}`, "Open in Timeline"] };
  }
  if (hit.kind === "run" && ev && !hit.arc.live) {
    // The mark under the pointer first, then the run it belongs to, compact.
    const arc = hit.arc;
    const done = byId.get(arc.run);
    const x = (done && done.extra) || {};
    const evs = arc.events || [];
    return {
      tier: ev.tier,
      nodes: [
        ...eventNodes(h, fmt, ev, hit.tick, true),
        h("div", { class: "tip__run" },
          h("p", { class: "tip__kicker" }, "part of the run"),
          h("p", { class: "tip__runline" }, h("b", {}, PHASES[arc.phase] || arc.phase || "run")),
          h("p", { class: "tip__stats" }, `${fmt.usd(x.cost_usd)} · ${x.turns ?? "–"} turns · ${x.model || "–"} · ${evs.length} events`),
          ...tierBar(h, evs)),
      ],
      link: [`?view=timeline#${ev.id}`, "Open in Timeline"],
    };
  }
  if (hit.kind === "run") {
    const arc = hit.arc;
    const evs = arc.events || [];
    if (arc.live) {
      const act = snap.activity || {};
      const since = act.phase && act.phase.since;
      return {
        tier: "live",
        nodes: [
          h("p", { class: "tip__kicker tip__kicker--live" }, "Running now"),
          h("p", { class: "tip__title" }, PHASES[arc.phase] || arc.phase || "a phase"),
          since ? h("p", { class: "tip__stats" }, `since ${fmt.clock(since)} · ${fmt.ago(since).replace(" ago", "")} so far`) : null,
          h("p", { class: "tip__muted" }, "The green arc grows while the phase runs. The dots on its tip are agents writing right now."),
        ],
      };
    }
    const done = byId.get(arc.run);
    const x = (done && done.extra) || {};
    const first = evs[0];
    const ringRuns = hit.ring.arcs.filter((a) => !a.live);
    const idx = ringRuns.indexOf(arc);
    return {
      tier: "run",
      nodes: [
        h("p", { class: "tip__kicker" }, `cycle ${hit.ring.cycle} · run ${idx + 1} of ${ringRuns.length}`),
        h("p", { class: "tip__title" }, PHASES[arc.phase] || arc.phase || "run"),
        h("div", { class: "tip__figs" },
          h("span", {}, h("b", {}, fmt.usd(x.cost_usd)), "cost"),
          h("span", {}, h("b", {}, String(x.turns ?? "–")), "turns"),
          h("span", {}, h("b", {}, x.model || "–"), "model")),
        first && done ? h("p", { class: "tip__stats" }, clockSpan(fmt, first.ts, done.ts)) : null,
        h("p", { class: "tip__sub" }, `${evs.length} events`),
        ...tierBar(h, evs),
        evs.length ? h("p", { class: "tip__muted" }, "Busiest: ", topActors(evs).map(([a, c], i) => [i ? ", " : "", h("span", { class: "tip__actor" }, a), ` ${c}`])) : null,
      ],
      link: first ? [`?view=timeline#${first.id}`, "Open in Timeline"] : null,
    };
  }
  if (hit.kind === "ring") {
    const ring = hit.ring;
    const evs = (snap.events || []).filter((e) => e.cycle === ring.cycle);
    const runs = evs.filter((e) => e.event === "run.completed");
    const cost = runs.reduce((s, e) => s + (Number(e.extra && e.extra.cost_usd) || 0), 0);
    const oldest = evs[evs.length - 1];
    const newest = evs[0];
    return {
      tier: "ring",
      nodes: [
        h("p", { class: "tip__kicker" }, ring.cycle === 0 ? "cycle 0 · before the first cycle" : ring.open ? "this cycle is open" : "a finished cycle"),
        h("p", { class: "tip__title" }, ring.cycle === 0 ? "Planning" : `Cycle ${ring.cycle}`),
        h("div", { class: "tip__figs" },
          h("span", {}, h("b", {}, fmt.usd(cost)), "cost"),
          h("span", {}, h("b", {}, String(runs.length)), "runs"),
          h("span", {}, h("b", {}, String(evs.length)), "events")),
        oldest && newest ? h("p", { class: "tip__stats" }, clockSpan(fmt, oldest.ts, newest.ts)) : null,
        ...tierBar(h, evs),
      ],
      link: [`?view=timeline#c${ring.cycle}`, "Open in Timeline"],
    };
  }
  if (hit.kind === "pin") {
    const w = (snap.waiting || []).find((x) => x.key === hit.pin.key);
    if (!w) return null;
    return {
      tier: "ceo",
      nodes: [
        h("p", { class: "tip__kicker tip__kicker--attention" }, w.kind === "question" ? `question ${w.id} · waiting on you` : `${w.gate} gate · waiting on you`),
        h("p", { class: "tip__title" }, w.title),
        h("p", { class: "tip__muted" }, "The outer ring stays open at the top until you answer. Each pin is one thing waiting."),
      ],
    };
  }
  return null;
}

// One card for the whole page, positioned in the viewport so the phone's cropped horizon never clips it.
let card = null;

function ensureCard(h) {
  if (!card) {
    card = h("div", { class: "tip", role: "tooltip", hidden: true });
    document.body.append(card);
  }
  return card;
}

function place(el, x, y) {
  const pad = 14;
  const w = el.offsetWidth;
  const hgt = el.offsetHeight;
  let left = x + 18;
  let top = y + 18;
  if (left + w + pad > window.innerWidth) left = x - w - 18;
  if (top + hgt + pad > window.innerHeight) top = y - hgt - 18;
  el.style.transform = `translate(${Math.max(pad, left)}px, ${Math.max(pad, top)}px)`;
}

export function attachInspector(host, svgEl, ctx) {
  const { h } = ctx;
  const tip = ensureCard(h);
  let shownKey = null;
  let pinned = false;
  let owner = false;

  const hide = () => {
    if (!owner) return;
    shownKey = null;
    pinned = false;
    owner = false;
    tip.hidden = true;
    tip.classList.remove("is-pinned");
    highlight(svgEl, null);
  };
  const show = (hit, x, y, pin) => {
    const snap = svgEl.__snapshot;
    const c = hit && snap ? cardFor(hit, snap, ctx) : null;
    if (!c) {
      if (!pinned) hide();
      return;
    }
    owner = true;
    if (hit.key !== shownKey || pin !== pinned) {
      shownKey = hit.key;
      const foot = pin && c.link ? h("p", { class: "tip__foot" }, h("a", { href: c.link[0] }, `${c.link[1]} →`)) : !pin ? h("p", { class: "tip__hint" }, "tap or click to pin") : null;
      tip.replaceChildren(...c.nodes.filter(Boolean), foot);
      tip.dataset.tier = c.tier || "";
      tip.classList.toggle("is-pinned", pin);
      if (tip.hidden) {
        tip.hidden = false;
        tip.classList.remove("is-in");
        void tip.offsetWidth;
        tip.classList.add("is-in");
      }
      highlight(svgEl, hit);
    }
    pinned = pin;
    place(tip, x, y);
  };

  svgEl.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || pinned) return;
    const hit = hitTest(svgEl, e.clientX, e.clientY);
    if (!hit || hit.kind === "centre") hide();
    else show(hit, e.clientX, e.clientY, false);
  });
  svgEl.addEventListener("pointerleave", (e) => {
    if (e.pointerType === "mouse" && !pinned) hide();
  });
  svgEl.addEventListener("click", (e) => {
    const hit = hitTest(svgEl, e.clientX, e.clientY);
    if (!hit || hit.kind === "centre" || (pinned && hit.key === shownKey)) {
      hide();
      return;
    }
    e.stopPropagation();
    pinned = false;
    shownKey = null;
    show(hit, e.clientX, e.clientY, true);
  });
  document.addEventListener("click", (e) => {
    if (!pinned || !owner) return;
    if (tip.contains(e.target)) {
      if (e.target.closest("a")) setTimeout(hide, 0);
      return;
    }
    hide();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hide();
  });
  window.addEventListener("scroll", () => {
    if (!pinned) hide();
  }, { passive: true });
  // Hidden with its view: a view switch leaves no card floating over the next page.
  new MutationObserver(() => {
    if (host.closest("section[hidden]")) hide();
  }).observe(host.closest("section") || host, { attributes: true, attributeFilter: ["hidden"] });
  svgEl.style.cursor = "crosshair";
}

// The legend: what each mark means. Hovering (or tapping) an entry isolates those marks in the rings.
export function legend(svgEl, ctx, { live = true } = {}) {
  const { h, svg } = ctx;
  const sw = (...shapes) => svg("svg", { class: "key__glyph", viewBox: "0 0 28 16", "aria-hidden": "true", focusable: "false" }, shapes);
  const items = [
    ["rings", "Ring", "one cycle; the oldest sits inside", sw(svg("path", { class: "k-track", d: "M3 15 A13 13 0 0 1 25 15" }))],
    ["arcs", "Arc", "one phase run; longer cost more", sw(svg("path", { class: "k-track", d: "M3 15 A13 13 0 0 1 25 15" }), svg("path", { class: "k-arc", d: "M5.5 9 A13 13 0 0 1 18 3.5" }))],
    ["ceo", "Your decisions", "approvals and answers", sw(svg("line", { class: "k-tick k-tick--ceo", x1: 14, y1: 1, x2: 14, y2: 15 }))],
    ["executive", "Leads", "plans, specs, rulings", sw(svg("line", { class: "k-tick", x1: 14, y1: 3, x2: 14, y2: 13 }))],
    ["execution", "Builders", "code, tests, reviews", sw(svg("line", { class: "k-tick", x1: 14, y1: 5, x2: 14, y2: 11 }))],
    ["latest", "Latest", "the newest event", sw(svg("circle", { class: "k-beacon", cx: 14, cy: 8, r: 3 }))],
  ];
  if (live) items.push(["live", "Live", "running now", sw(svg("circle", { class: "k-live", cx: 14, cy: 8, r: 3.5 }))]);
  const list = h("ul", { class: "key", "aria-label": "How to read the rings" }, items.map(([k, name, what, glyph]) => {
    const li = h("button", { type: "button", class: "key__item", "data-only": k }, glyph, h("span", {}, h("b", {}, name), " ", h("span", { class: "key__what" }, what)));
    const on = () => (svgEl.dataset.only = k);
    const off = () => delete svgEl.dataset.only;
    li.addEventListener("pointerenter", on);
    li.addEventListener("pointerleave", off);
    li.addEventListener("focus", on);
    li.addEventListener("blur", off);
    li.addEventListener("click", () => (svgEl.dataset.only === k ? off() : on()));
    return h("li", {}, li);
  }));
  return h("div", { class: "legend" }, list);
}
