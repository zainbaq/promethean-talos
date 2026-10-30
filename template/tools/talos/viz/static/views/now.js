// Now view (ADR-0005 point 2; components.md Shell, The rings, Growth edge, Waiting on you, Cycle figures, Summary lines).
// mount builds the static structure once; update patches nodes in place, keyed by stable ids.
import { buildRings, updateRings } from "../rings.js";
import { attachInspector, legend } from "../inspect.js";

export const id = "now";
export const title = "Now";

const R = new WeakMap();
const GATE_NAME = { charter: "Charter", plan: "Plan", design: "Design", release: "Release" };

function put(node, s) {
  s = String(s);
  if (node.textContent !== s) node.textContent = s;
}

function setClass(node, cls) {
  if (node.className !== cls) node.className = cls;
}

export function mount(root, ctx) {
  const { h } = ctx;
  root.classList.add("main--split");
  const r = { root, phaseSig: "", metaSig: "", noteSig: "", srSig: "", sumSig: ["", ""], svg: null, empty: null };

  r.phase = h("h1", { class: "phase", id: "phase", "aria-live": "polite" });
  r.meta = h("p", { class: "phase__meta" });
  r.centre = h("div", { class: "rings__centre" }, r.phase, r.meta);
  r.sr = h("p", { class: "sr-only" });
  r.horizon = h("div", { class: "horizon has-edge" }, r.centre, r.sr);

  r.edgeCount = h("span", { class: "count" });
  r.agents = h("ul", { class: "agents" });
  r.note = h("p", { class: "edge__note" });
  r.edge = h("section", { class: "edge", "aria-labelledby": "edge-h" }, h("h2", { id: "edge-h", class: "section-h" }, "Growth edge ", r.edgeCount), r.agents, r.note);

  r.cycleName = h("span");
  r.cycleCount = h("span", { class: "count" });
  const fig = (label, unit) => {
    const val = h("span", { class: "val" });
    const sub = h("dd", { class: "sub" });
    return { val, sub, node: h("div", {}, h("dt", {}, label), h("dd", { class: "num" }, val, unit ? h("span", { class: "unit" }, unit) : null), sub) };
  };
  r.fElapsed = fig("Elapsed");
  r.fSpend = fig("Spend");
  r.fTokens = fig("Tokens", "M");
  r.budget = h("p", { class: "budget" });
  r.cycle = h("section", { class: "cycle", "aria-labelledby": "cycle-h" },
    h("h2", { id: "cycle-h", class: "section-h" }, r.cycleName, " ", r.cycleCount),
    h("dl", { class: "figures" }, r.fElapsed.node, r.fSpend.node, r.fTokens.node), r.budget);

  r.waitCount = h("span", { class: "count count--attention", "aria-live": "polite" });
  r.waits = h("ol", { class: "waits" });
  r.waiting = h("section", { class: "waiting", "aria-labelledby": "waiting-h" }, h("h2", { id: "waiting-h", class: "section-h" }, "Waiting on you ", r.waitCount), r.waits);

  r.backlog = h("p", { class: "summary-line" });
  r.latest = h("p", { class: "summary-line" });
  r.summaries = h("section", { class: "cycle summaries", "aria-labelledby": "backlog-h" },
    h("h2", { id: "backlog-h", class: "section-h" }, "Backlog"), r.backlog,
    h("h2", { id: "latest-h", class: "section-h" }, "Latest in the ledger"), r.latest);

  r.legendSlot = h("div", { class: "legend-slot" });
  root.append(h("div", { class: "picture" }, r.horizon, r.legendSlot, r.edge, r.cycle), h("div", { class: "panel" }, r.waiting, r.summaries));
  R.set(root, r);
}

export function update(root, snapshot, ctx) {
  const r = R.get(root);
  const first = ctx.diff === null;
  renderPhase(r, snapshot, ctx);
  renderRings(r, snapshot, ctx, first);
  renderEdge(r, snapshot, ctx, first);
  renderCycle(r, snapshot, ctx, first);
  renderWaiting(r, snapshot, ctx, first);
  renderSummaries(r, snapshot, ctx);
}

// ---------- the centre: phase word, meta, screen-reader sentence ----------
function renderPhase(r, s, ctx) {
  const { h, fmt } = ctx;
  const act = s.activity || {};
  const running = !!(act.phase && act.phase.status === "running");
  const broken = (s.errors || []).some((e) => e.block === "ledger" || e.block === "state") || ctx.params.get("fresh") === "error";
  const live = running && !broken;
  setClass(r.horizon, `horizon has-edge${live ? " is-live" : ""}${broken ? " is-error" : ""}`);

  const phaseSig = broken ? "error" : running ? `run:${act.phase.name}` : "idle";
  if (phaseSig !== r.phaseSig) {
    r.phaseSig = phaseSig;
    if (broken) r.phase.replaceChildren("Record unreadable");
    else if (running) r.phase.replaceChildren(h("span", { class: "sr-only" }, "Running "), h("code", { class: "phase__live", "data-phase": act.phase.name || "" }, (act.phase.name || "running").replace(/^cycle-/, "")));
    else r.phase.replaceChildren("Idle");
  }

  const c = s.cycle || { number: 0, open: false };
  const word = c.number === 0 ? "planning" : c.open ? "open" : `closed${c.ended_at ? ` ${fmt.clock(c.ended_at)}` : ""}`;
  const cyc = `cycle ${c.number} ${word}`;
  let sig;
  let nodes;
  if (broken) {
    const reason = s.errors && s.errors[0] && s.errors[0].reason ? s.errors[0].reason : "record unreadable";
    sig = `${reason} since ${fmt.clock(s.generated_at)}`;
    nodes = [sig];
  } else if (running) {
    const minutes = Math.round((ctx.now() - Date.parse(act.phase.since)) / 60000);
    sig = `run|${act.phase.since}|${fmt.hm(minutes)}|${cyc}`;
    nodes = [h("span", { class: "phase__line" }, "running · ", h("span", { class: "num" }, fmt.hm(minutes))), h("span", { class: "phase__line" }, c.number === 0 ? "planning" : `cycle ${c.number} · ${c.open ? "open" : "closed"}`)];
  } else if (act.last_run) {
    sig = `idle|${cyc}|${act.last_run.phase}|${act.last_run.ts}`;
    nodes = [h("span", { class: "phase__line" }, c.number === 0 ? "planning" : `cycle ${c.number} · ${c.open ? "open" : "closed"}`), h("span", { class: "phase__line" }, `last: ${act.last_run.phase} ${fmt.clock(act.last_run.ts).slice(0, 5)}`)];
  } else {
    const none = s.counts && s.counts.events === 0 ? "no events yet" : "no runs yet";
    sig = `idle|${cyc}|${none}`;
    nodes = [h("span", { class: "phase__line" }, c.number === 0 ? "planning" : `cycle ${c.number} · ${c.open ? "open" : "closed"}`), h("span", { class: "phase__line" }, none)];
  }
  if (sig !== r.metaSig) {
    r.metaSig = sig;
    r.meta.replaceChildren(...nodes);
  }

  const cycles = new Set((s.events || []).map((e) => e.cycle));
  cycles.add(c.number);
  const w = (s.waiting || []).length;
  const gaps = w === 0 ? "the ring is sealed." : `${w} ${w === 1 ? "gap" : "gaps"} waiting on you.`;
  const sr = `Growth rings: ${cycles.size} cycles, ${s.counts ? s.counts.events : (s.events || []).length} events; ${gaps}`;
  if (sr !== r.srSig) {
    r.srSig = sr;
    put(r.sr, sr);
  }
}

// ---------- the rings: drawn complete on first paint, patched afterwards ----------
function renderRings(r, s, ctx, first) {
  if (!r.svg) {
    const el = ctx.svg("svg", { class: "rings", viewBox: "0 0 400 400", "aria-hidden": "true", focusable: "false" });
    buildRings(el, s, { edge: true });
    r.horizon.insertBefore(el, r.centre);
    r.svg = el;
    attachInspector(r.horizon, el, ctx);
    r.legendSlot.append(legend(el, ctx));
    return;
  }
  const d = ctx.diff;
  if (first || !d) return;
  if (d.events.added.length || d.waiting.added.length || d.waiting.removed.length || d.cycle || d.activity || d.spend || d.counts) {
    updateRings(r.svg, s, d, { edge: true });
  }
}

// ---------- growth edge ----------
function lastRunSentence(ctx, run) {
  const { h, fmt } = ctx;
  if (!run) return ["No runs yet."];
  return ["Last run ", h("code", {}, run.phase), ` on ${run.model} finished `, h("time", {}, fmt.clock(run.ts)), `, ${run.turns} turns, ${fmt.usd(run.cost_usd)}.`];
}

function renderEdge(r, s, ctx, first) {
  const { h, fmt, motion } = ctx;
  const act = s.activity || { status: "unavailable", agents: [] };
  const windowS = act.window_seconds ?? 120;
  const isRecent = (a) => (a.state ? a.state === "recent" : (a.seconds_ago || 0) > windowS);
  const agents = act.agents || [];
  const ordered = [...agents.filter((a) => !isRecent(a)), ...agents.filter(isRecent)];
  const active = agents.filter((a) => !isRecent(a)).length;
  const unavailable = act.status === "unavailable";

  setClass(r.edgeCount, unavailable ? "count" : active > 0 ? "count count--signal" : "count");
  const countText = unavailable ? "unavailable" : String(active);
  if (first) put(r.edgeCount, countText);
  else motion.tick(r.edgeCount, countText);

  // chips, keyed by role|session|transcript (the same key rings.js gives the edge dots)
  const keyOf = (a) => `${a.role}|${a.session || ""}|${a.transcript || ""}`;
  const have = new Map();
  for (const li of r.agents.children) if (!li.hasAttribute("data-leaving")) have.set(li.getAttribute("data-key"), li);
  const wanted = new Set();
  const lis = [];
  for (const a of ordered) {
    const key = keyOf(a);
    wanted.add(key);
    let li = have.get(key);
    const recent = isRecent(a);
    // "on ITEM-nnnn" from the deriver, else "on <phase>" only for the session that runs the phase, else nothing (ADR-0010).
    const inRun = act.phase && act.phase.status === "running" && a.session === act.phase.session;
    const what = a.item ?? (inRun ? act.phase.name : null);
    if (!li) {
      li = h("li", { class: "agent", "data-key": key },
        h("span", { class: "agent__dot", "aria-hidden": "true" }), h("span", { class: "agent__name" }, a.role), " ",
        h("span", { class: "agent__on" }), " ", h("span", { class: "agent__since" }));
      r.agents.append(li);
      if (!first) motion.enter(li);
    }
    setClass(li, recent ? "agent agent--recent" : "agent");
    const on = li.querySelector(".agent__on");
    const onSig = what == null ? "" : `${recent ? "was on" : "on"}|${what}`;
    if (li.__on !== onSig) {
      li.__on = onSig;
      on.hidden = what == null;
      if (what == null) on.replaceChildren();
      else on.replaceChildren(recent ? "was on " : "on ", h("code", {}, what));
    }
    put(li.querySelector(".agent__since"), `${fmt.clock(a.last_write_at)} · ${fmt.ago(a.last_write_at)}`);
    lis.push(li);
  }
  for (const [key, li] of have) if (!wanted.has(key)) motion.leave(li);
  let cursor = r.agents.firstElementChild;
  for (const li of lis) {
    while (cursor && cursor.hasAttribute("data-leaving") && cursor !== li) cursor = cursor.nextElementSibling;
    if (cursor === li) cursor = li.nextElementSibling;
    else r.agents.insertBefore(li, cursor);
  }
  r.agents.hidden = lis.length === 0 && !r.agents.querySelector("[data-leaving]");

  let sig;
  let nodes;
  if (unavailable) {
    sig = `unavailable|${JSON.stringify(act.last_run)}`;
    nodes = [h("strong", {}, "Activity unavailable."), " No transcript folder exists for this record, so nobody can be shown as active. Everything else on this page comes from the ledger. ", ...lastRunSentence(ctx, act.last_run)];
  } else if (active > 0) {
    sig = "active";
    nodes = ["Active means a transcript write in the last 2 minutes; a hollow dot wrote within 5."];
  } else {
    sig = `nobody|${JSON.stringify(act.last_run)}`;
    nodes = [h("strong", {}, "Nobody active."), " ", ...lastRunSentence(ctx, act.last_run), " Active means a transcript write in the last 2 minutes."];
  }
  if (sig !== r.noteSig) {
    r.noteSig = sig;
    r.note.replaceChildren(...nodes);
  }
}

// ---------- cycle figures ----------
function setFigure(f, value, sub, ctx, first) {
  if (first) put(f.val, value);
  else ctx.motion.tick(f.val, value);
  put(f.sub, sub);
}

function renderCycle(r, s, ctx, first) {
  const { fmt, h } = ctx;
  const c = s.cycle || { number: 0, open: false };
  put(r.cycleName, `Cycle ${c.number}`);
  setClass(r.cycleCount, c.number === 0 ? "count" : c.open ? "count count--signal" : "count");
  put(r.cycleCount, c.number === 0 ? "planning" : c.open ? "open" : "closed");

  const hhmm = (iso) => fmt.clock(iso).slice(0, 5);
  let sub = "n/a";
  if (c.started_at && c.ended_at) sub = `${hhmm(c.started_at)} to ${hhmm(c.ended_at)}`;
  else if (c.started_at) sub = `since ${fmt.clock(c.started_at)}`;
  setFigure(r.fElapsed, fmt.hm(c.elapsed_minutes ?? 0), sub, ctx, first);

  const ev = (s.spend && s.spend.events) || { runs: 0, cost_usd: 0, tokens: 0 };
  setFigure(r.fSpend, fmt.usd(ev.cost_usd), `${ev.runs} runs`, ctx, first);

  const tr = s.spend && s.spend.transcripts;
  if (tr && tr.available) setFigure(r.fTokens, fmt.millions(tr.tokens), `${tr.calls} model calls, transcripts`, ctx, first);
  else setFigure(r.fTokens, fmt.millions(ev.tokens), "runs only, no transcripts", ctx, first);

  const budget = c.budget ? ["Budget: ", h("strong", {}, c.budget), "."] : ["Budget: not set."];
  const sig = c.budget || "";
  if (r.budget.__sig !== sig) {
    r.budget.__sig = sig;
    r.budget.replaceChildren(...budget);
  }
}

// ---------- Waiting on you ----------
function buildCardContent(w, ctx) {
  const { h, fmt } = ctx;
  const gateName = GATE_NAME[w.gate] || "";
  let kind;
  if (w.kind === "question") kind = ["Question ", h("code", {}, w.id), ` · asked ${fmt.clock(w.asked_at)} by ${w.asked_by}`];
  else if (w.gate === "release") kind = [`Release gate · verified ${fmt.clock(w.proposed_at)}`];
  else kind = [`${gateName} gate · proposed ${fmt.clock(w.proposed_at)}`];

  let heading;
  if (w.kind === "question") heading = [w.title];
  else if (w.gate === "release") {
    const prefix = `Release ${w.ref}: `;
    heading = [h("a", { href: `?view=work#${w.ref}` }, w.ref), ` ${w.title.startsWith(prefix) ? w.title.slice(prefix.length) : w.title}`];
  } else {
    const prefix = `${gateName} gate: `;
    heading = [w.title.startsWith(prefix) ? w.title.slice(prefix.length) : w.title];
  }

  let body = null;
  if (w.kind === "question" && w.context) {
    const at = w.context.indexOf("Proposed default:");
    body = h("p", { class: "wait__body" }, at < 0 ? w.context : [w.context.slice(0, at), h("strong", {}, w.context.slice(at))]);
  }

  let meta;
  if (w.kind === "question") meta = [w.options ? `Options: ${w.options}` : "", w.options && w.ref ? " · " : "", w.ref ? ["ref ", h("code", {}, w.ref)] : null];
  else if (w.gate === "release") meta = w.proposed_event ? [h("code", {}, w.proposed_event), " · no ", h("code", {}, "release.approved"), " event"] : ["no ", h("code", {}, "release.approved"), " event"];
  else meta = [h("code", {}, w.proposed_event), " · no ", h("code", {}, `${w.gate}.approved`), " event"];

  const safe = typeof w.command === "string" && !/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]/.test(w.command);
  const canCopy = safe && typeof navigator !== "undefined" && !!navigator.clipboard && typeof navigator.clipboard.writeText === "function";
  const btn = h("button", { type: "button", class: "btn", hidden: !canCopy }, "Copy");
  if (canCopy) {
    let timer = null;
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(w.command);
      } catch {
        return;
      }
      ctx.motion.tick(btn, "Copied");
      clearTimeout(timer);
      timer = setTimeout(() => ctx.motion.tick(btn, "Copy"), 1500);
    });
  }
  const cmd = h("div", { class: "cmd" }, h("code", {}, w.command), canCopy || !safe ? null : h("span", { class: "cmd__hint" }, "select to copy"), safe ? btn : null);
  return [h("p", { class: "wait__kind" }, kind), h("h3", { class: "wait__title" }, heading), body, h("p", { class: "wait__meta" }, meta), cmd];
}

function retire(li, ctx, r) {
  const { h, fmt, motion } = ctx;
  const w = li.__w;
  li.classList.add("is-leaving");
  const kind = li.querySelector(".wait__kind");
  if (kind && w) {
    if (w.kind === "question") kind.replaceChildren("Question ", h("code", {}, w.id), ` · answered ${fmt.clock(new Date(ctx.now()).toISOString())} by ${w.asked_by}`);
    else kind.replaceChildren(`${GATE_NAME[w.gate] || ""} gate · approved`);
  }
  const wait = motion.durationMs("--dur-1");
  if (!wait) {
    li.remove();
    syncEmpty(r, ctx, false);
    return;
  }
  setTimeout(() => motion.leave(li).then(() => syncEmpty(r, ctx, false)), wait);
}

function syncEmpty(r, ctx, first) {
  const open = [...r.waits.children].some((li) => !li.classList.contains("is-leaving"));
  if (open && r.empty) {
    r.empty.remove();
    r.empty = null;
  }
  if (open || r.waits.children.length > 0) return;
  if (!r.empty) {
    r.empty = ctx.h("p", { class: "empty" }, "Nothing is waiting on you. The ring is sealed.");
    r.waiting.append(r.empty);
    if (!first) ctx.motion.enter(r.empty);
  }
}

function renderWaiting(r, s, ctx, first) {
  const { motion } = ctx;
  const waiting = s.waiting || [];
  const n = waiting.length;
  if (first) put(r.waitCount, n);
  else motion.tick(r.waitCount, n);

  const have = new Map();
  for (const li of r.waits.children) if (!li.classList.contains("is-leaving")) have.set(li.getAttribute("data-key"), li);
  const wanted = new Set(waiting.map((w) => w.key));

  const mutate = () => {
    const lis = [];
    for (const w of waiting) {
      let li = have.get(w.key);
      const sig = JSON.stringify(w);
      if (!li) {
        li = ctx.h("li", { class: "wait", "data-key": w.key });
        r.waits.append(li);
        if (!first) motion.enter(li);
      }
      if (li.__sig !== sig) {
        li.__sig = sig;
        li.__w = w;
        li.replaceChildren(...buildCardContent(w, ctx).filter(Boolean));
      }
      lis.push(li);
    }
    let cursor = r.waits.firstElementChild;
    for (const li of lis) {
      while (cursor && cursor !== li && cursor.classList.contains("is-leaving")) cursor = cursor.nextElementSibling;
      if (cursor === li) cursor = li.nextElementSibling;
      else r.waits.insertBefore(li, cursor);
    }
  };
  const gone = [...have].filter(([k]) => !wanted.has(k)).map(([, li]) => li);
  for (const li of gone) retire(li, ctx, r);
  if (first || (!gone.length && !waiting.some((w) => !have.has(w.key)))) mutate();
  else motion.flip(r.waits, mutate);
  if (n > 0 && r.empty) {
    r.empty.remove();
    r.empty = null;
  }
  syncEmpty(r, ctx, first);
}

// ---------- summaries ----------
function renderSummaries(r, s, ctx) {
  const { h, fmt } = ctx;
  const items = s.items || [];
  const total = s.counts && s.counts.items ? s.counts.items.total : items.length;
  // Statuses are listed in the order they first appear in the item list (this reproduces both approved mockups).
  const order = [];
  for (const it of items) if (!order.includes(it.status)) order.push(it.status);
  const count = (st) => items.filter((it) => it.status === st).length;
  const parts = order.map((st) => `${count(st)} ${st.replace("_", " ")}`);
  const backlogSig = `${total}|${parts.join(",")}`;
  if (backlogSig !== r.sumSig[0]) {
    r.sumSig[0] = backlogSig;
    if (!total) r.backlog.replaceChildren("No items yet.");
    else r.backlog.replaceChildren(h("strong", {}, `${total} items`), `: ${parts.join(", ")}. `, h("a", { href: "?view=work" }, "Open Work"));
  }
  const ev = (s.events || [])[0];
  const latestSig = ev ? `${ev.id}|${ev.summary}|${s.counts.events}` : "none";
  if (latestSig !== r.sumSig[1]) {
    r.sumSig[1] = latestSig;
    if (!ev) r.latest.replaceChildren("No events yet.");
    else r.latest.replaceChildren(h("time", {}, fmt.clock(ev.ts)), " ", h("code", {}, ev.event), ` ${ev.summary} `, h("a", { href: "?view=timeline" }, `All ${s.counts.events} events`));
  }
}
