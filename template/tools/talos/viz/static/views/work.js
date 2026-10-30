// Work view (SPEC-0005; components.md Item glyph, Status scale, Band, Card, Report; motion rows 5 and 11).
// mount builds the static structure once; update patches nodes in place, keyed by item id, so scroll and focus survive.
import { glyph } from "../rings.js";
import { render } from "../markdown.js";

export const id = "work";
export const title = "Work";

const BANDS = [
  ["proposed", "Proposed"],
  ["ready", "Ready"],
  ["in_progress", "In progress"],
  ["completed", "Completed"],
  ["verified", "Verified"],
  ["blocked", "Blocked"],
];
// Statuses that have no band of their own land in a neighbour and say so, so no item is ever dropped.
const FOLD = { assigned: "ready", shipped: "verified", rejected: "blocked" };
const ALSO = { ready: "assigned", verified: "shipped", blocked: "rejected" };
const NONE = { completed: "none awaiting verification" };
const NO_REPORT = "No report yet. The first one is written at cycle close.";

const R = new WeakMap();

function put(node, s) {
  s = String(s);
  if (node.textContent !== s) node.textContent = s;
}

function bandOf(item) {
  const status = FOLD[item.status] || item.status;
  return BANDS.some(([k]) => k === status) ? status : "proposed"; // an unknown status still shows somewhere
}

function byPriority(a, b) {
  const pa = a.priority || "~";
  const pb = b.priority || "~";
  return pa < pb ? -1 : pa > pb ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

export function mount(root, ctx) {
  const { h } = ctx;
  const r = { root, bands: new Map(), strip: new Map(), cards: new Map(), reportSig: null, shown: new Map() };

  r.scale = h("nav", { class: "scale", "aria-label": "Status scale" });
  r.board = h("div", { class: "board", "aria-label": "Backlog by status" });
  for (const [key, label] of BANDS) {
    const count = h("span", { class: "count" });
    const headGlyph = glyph(key);
    const labelEl = h("span", {});
    const ul = h("ul", { class: "cards" });
    const section = h("section", { class: `band band--${key}`, "data-key": `band:${key}` },
      h("h2", { class: "band__h", id: `b-${key}` }, headGlyph, labelEl), ul);
    r.board.append(section);
    r.bands.set(key, { key, label, section, count, headGlyph, labelEl, ul, sig: null, n: -1 });

    const stripCount = h("span", { class: "count" });
    const stripGlyph = glyph(key);
    r.scale.append(h("a", { href: `#b-${key}` }, stripGlyph, h("span", {}, label), stripCount));
    r.strip.set(key, { count: stripCount, glyph: stripGlyph });
  }
  r.inner = h("div", { class: "report__inner" });
  r.article = h("article", { class: "report", "aria-label": "Latest cycle report" }, r.inner);
  root.append(h("h1", { class: "sr-only" }, "Work"), r.scale, r.board, r.article);
  R.set(root, r);
}

// ---------- cards ----------
function useOf(svgEl) {
  return svgEl.querySelector("use");
}

function buildCard(item, ctx) {
  const { h } = ctx;
  const li = h("li", { class: "card", id: item.id, "data-key": item.id },
    glyph(bandOf(item)),
    h("p", { class: "card__line" }),
    h("h3", { class: "card__title" }, h("a", { href: `#${item.id}` })),
    h("p", { class: "card__meta" }));
  return li;
}

function patchCard(r, li, item, band, ctx, animate) {
  const { h, fmt, motion } = ctx;
  const svgEl = li.querySelector(":scope > svg.glyph");
  const shown = r.shown.get(item.id);
  if (shown !== undefined && shown !== band) crossfade(svgEl, band, ctx, animate);
  else if (shown === undefined) svgEl.setAttribute("class", `glyph glyph--${band}`);
  r.shown.set(item.id, band);

  const waitingRelease = r.waitKeys.has(`gate:release:${item.id}`);
  const chips = [];
  if (item.id) chips.push(h("span", { class: "card__id" }, item.id));
  if (item.priority) chips.push(h("span", { class: item.priority === "P0" ? "chip chip--p0" : "chip" }, item.priority));
  if (item.risk) chips.push(h("span", { class: item.risk === "high" ? "chip chip--risk-high" : "chip" }, `risk ${item.risk}`));
  if (item.status === "assigned" || item.status === "shipped" || item.status === "rejected") chips.push(h("span", { class: "chip chip--status" }, item.status));
  if (item.status === "verified" && waitingRelease) chips.push(h("span", { class: "chip chip--status" }, "awaiting release"));
  const when = item.status === "verified" ? `verified ${fmt.clock(item.updated)}` : `created ${fmt.clock(item.created)}`;
  const where = item.branch ? (item.commit ? `${item.branch} @ ${item.commit}` : item.branch) : null;
  const meta = [
    item.owner ? h("span", { class: "owner" }, item.owner) : h("span", {}, "no owner"),
    item.spec ? h("span", {}, h("code", {}, item.spec)) : h("span", {}, "no spec"),
    where ? h("span", {}, h("code", {}, where)) : h("span", {}, "no branch"),
    h("span", {}, when),
  ];
  // The title link is never rebuilt, so focus on it survives an update; the two text lines are replaced only when they differ.
  const sig = JSON.stringify([chips.map((c) => c.className + c.textContent), meta.map((c) => c.className + c.textContent)]);
  if (li.__sig !== sig) {
    li.__sig = sig;
    const line = li.querySelector(":scope > .card__line");
    const metaEl = li.querySelector(":scope > .card__meta");
    line.replaceChildren();
    for (const c of chips) line.append(c, " ");
    metaEl.replaceChildren();
    for (const c of meta) metaEl.append(c, " ");
  }
  put(li.querySelector(":scope > .card__title > a"), item.title || item.id);
  void motion;
}

// Motion 11: two <use> elements, the new one fades in while the old one fades out.
function crossfade(svgEl, band, ctx, animate) {
  const old = useOf(svgEl);
  svgEl.setAttribute("class", `glyph glyph--${band}`);
  const next = ctx.svg("use", { href: `#g-${band}` });
  svgEl.append(next);
  if (!animate || ctx.motion.durationMs("--dur-2") === 0) {
    if (old) old.remove();
    return;
  }
  ctx.motion.enter(next);
  if (old) {
    old.setAttribute("data-leaving", "");
    setTimeout(() => old.remove(), ctx.motion.durationMs("--dur-2") + 20);
  }
}

// ---------- bands and strip ----------
function patchBand(r, band, items, ctx, animate) {
  const { h, motion } = ctx;
  const n = items.length;
  const also = ALSO[band.key];
  const hasAlso = also && items.some((i) => i.status === also);
  const sig = `${n > 0}|${hasAlso ? also : ""}`;
  band.count.className = band.key === "verified" && n > 0 ? "count count--signal" : "count";
  if (band.sig !== sig) {
    band.sig = sig;
    const parts = [`${band.label} `];
    if (n > 0) parts.push(band.count);
    if (hasAlso) parts.push(" ", h("span", { class: "band__also" }, `+ ${also}`));
    if (n === 0) parts.push(h("span", { class: "band__none" }, NONE[band.key] || "none"));
    band.labelEl.replaceChildren(...parts);
    band.count.textContent = String(n);
  } else if (animate && band.n !== n) motion.tick(band.count, String(n));
  else put(band.count, n);
  band.n = n;
  band.section.classList.toggle("is-empty", n === 0);
  band.headGlyph.classList.toggle("glyph--empty", n === 0);
  const s = r.strip.get(band.key);
  s.glyph.classList.toggle("glyph--empty", n === 0);
  s.count.className = band.key === "verified" && n > 0 ? "count count--signal" : "count";
  if (animate && s.count.textContent !== "" && s.count.textContent !== String(n)) motion.tick(s.count, String(n));
  else put(s.count, n);
}

export function update(root, snapshot, ctx) {
  const r = R.get(root);
  const items = snapshot.items || [];
  const animate = ctx.diff !== null;
  r.waitKeys = new Set((snapshot.waiting || []).map((w) => w.key));
  const total = items.length;
  r.scale.setAttribute("aria-label", `Status scale, ${total} items`);
  r.board.setAttribute("aria-label", `Backlog by status, ${total} items`);

  const grouped = new Map(BANDS.map(([k]) => [k, []]));
  for (const item of items) grouped.get(bandOf(item)).push(item);
  for (const list of grouped.values()) list.sort(byPriority);

  const ids = new Set(items.map((i) => i.id));
  let movedAny = false;
  const mutate = () => {
    for (const [cid, li] of r.cards) {
      if (ids.has(cid)) continue;
      r.cards.delete(cid);
      r.shown.delete(cid);
      if (animate) ctx.motion.leave(li);
      else li.remove();
    }
    for (const [key, list] of grouped) {
      const band = r.bands.get(key);
      let cursor = band.ul.firstElementChild;
      for (const item of list) {
        let li = r.cards.get(item.id);
        const fresh = !li;
        if (fresh) {
          li = buildCard(item, ctx);
          r.cards.set(item.id, li);
        } else if (li.parentElement !== band.ul) movedAny = true;
        while (cursor && cursor.hasAttribute("data-leaving") && cursor !== li) cursor = cursor.nextElementSibling;
        if (cursor === li) cursor = li.nextElementSibling;
        else band.ul.insertBefore(li, cursor);
        patchCard(r, li, item, key, ctx, animate);
        if (fresh && animate) ctx.motion.enter(li);
      }
    }
  };
  if (animate && ctx.diff.items.moved.length) ctx.motion.flip(r.board, mutate, { token: "--dur-3" });
  else mutate();
  void movedAny;

  for (const [key, list] of grouped) patchBand(r, r.bands.get(key), list, ctx, animate);
  renderReport(r, snapshot.report, ctx);
}

// ---------- report ----------
function renderReport(r, report, ctx) {
  const { h, fmt } = ctx;
  const sig = report ? `${report.path}|${report.modified_at}|${report.markdown}` : "none";
  if (r.reportSig === sig) return;
  r.reportSig = sig;
  if (!report) {
    r.inner.replaceChildren(h("p", { class: "report__empty" }, NO_REPORT));
    return;
  }
  const kicker = h("p", { class: "report__kicker" }, h("span", {}, report.path), h("span", {}, `generated ${fmt.clock(report.modified_at)}`));
  let body;
  try {
    body = render(report.markdown, h);
    for (const hd of body.querySelectorAll("h3")) if (hd.textContent.trim() === "Needs your decision") hd.classList.add("is-decision");
  } catch {
    body = h("div", {}, h("pre", {}, String(report.markdown ?? "")), h("p", { class: "report__note" }, "Report could not be parsed; shown as written."));
  }
  r.inner.replaceChildren(kicker, body);
}
