// motion.js: the only file calling startViewTransition or Element.animate (ADR-0004). Rows refer to company/design/motion.md.
import { h } from "./dom.js";

export function reduced() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches || document.documentElement.dataset.motion === "reduce";
}

export function durationMs(token) {
  if (reduced()) return 0;
  const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(token));
  return Number.isFinite(v) ? v : 0;
}

function easing(token) {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim() || "ease";
}

// Row 1: view switch. The DOM swap is always the same; a view transition only decorates it.
export function switchView(fromSection, toSection) {
  const swap = () => {
    if (fromSection && fromSection !== toSection) fromSection.hidden = true;
    toSection.hidden = false;
  };
  if (fromSection === toSection) return Promise.resolve();
  if (typeof document.startViewTransition === "function" && !reduced()) {
    const t = document.startViewTransition(swap);
    return t.finished.catch(() => {});
  }
  swap();
  enter(toSection);
  return Promise.resolve();
}

// Trigger first, DOM second, animation third: the attribute is applied and flushed, then removed so the CSS transition runs.
export function enter(node) {
  node.setAttribute("data-entering", "");
  void getComputedStyle(node).opacity;
  requestAnimationFrame(() => node.removeAttribute("data-entering"));
}

export function leave(node) {
  node.setAttribute("data-leaving", "");
  const ms = durationMs("--dur-2");
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      node.removeEventListener("transitionend", onEnd);
      const parent = node.parentElement;
      if (parent && parent.querySelector(":scope > [data-key]")) flip(parent, () => node.remove());
      else node.remove();
      resolve(node);
    };
    const onEnd = (e) => { if (e.target === node) finish(); };
    node.addEventListener("transitionend", onEnd);
    setTimeout(finish, ms + 20);
  });
}

// FLIP for keyed children: measure, mutate, invert, play.
export function flip(container, mutate, { token = "--dur-2" } = {}) {
  const before = new Map();
  for (const child of container.children) {
    const key = child.getAttribute("data-key");
    if (key !== null) before.set(key, child.getBoundingClientRect());
  }
  mutate();
  const ms = durationMs(token);
  if (!ms) return;
  for (const child of container.children) {
    const key = child.getAttribute("data-key");
    const from = before.get(key);
    if (!from) continue;
    const to = child.getBoundingClientRect();
    const dx = from.left - to.left;
    const dy = from.top - to.top;
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue;
    child.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], { duration: ms, easing: easing("--ease-in-out") });
  }
}

// Row 5: only changed characters roll. The DOM holds the final text at every moment; the old glyph is a pseudo-element.
export function tick(el, newText) {
  newText = String(newText);
  const old = el.textContent;
  if (old === newText) return;
  const ms = durationMs("--dur-2");
  if (!ms || !el.isConnected || !old) {
    el.textContent = newText;
    return;
  }
  const oldC = [...old];
  const newC = [...newText];
  const same = oldC.length === newC.length;
  el.textContent = "";
  const ease = easing("--ease-out");
  const running = [];
  newC.forEach((c, i) => {
    if (same && oldC[i] === c) {
      el.append(c);
      return;
    }
    const inner = h("span", { class: "roll__new" }, c);
    const outer = h("span", { class: "roll", "data-old": i < oldC.length ? oldC[i] : "" }, inner);
    el.append(outer);
    running.push(inner.animate([{ transform: "translateY(0.6em)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: ms, easing: ease }));
    running.push(outer.animate([{ transform: "none", opacity: 1 }, { transform: "translateY(-0.6em)", opacity: 0 }], { duration: ms, easing: ease, pseudoElement: "::after" }));
  });
  Promise.allSettled(running.map((a) => a.finished)).then(() => {
    if (el.textContent === newText && el.querySelector(".roll")) el.textContent = newText;
  });
}

// Row 2: keep what the reader sees where it is when a row lands above the viewport.
export function insertKeepingScroll(parent, node, before) {
  parent.insertBefore(node, before ?? null);
  const rect = node.getBoundingClientRect();
  if (rect.bottom < 0) document.scrollingElement.scrollTop += rect.height;
}
