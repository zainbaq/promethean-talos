// control.js: the control room. Gate and question cards above the page, a chat along the bottom, the preset switch.
// It writes only through /api/control/*, and what comes back is the next snapshot. Hidden unless the snapshot offers a
// control block and the server says this page may write.
import { h } from "./dom.js";

const PRESETS = ["lite", "medium", "heavy"];
const THREAD_EVENTS = /^(question\.asked|[a-z-]+\.proposed|run\.stopped|cycle\.ended|release\.shipped|message\.acknowledged)$/;
const CONFIRM_MS = 4000;

export function createControl({ query, sessionUrl = "/api/session" }) {
  const refs = { cards: new Map() };
  let session = null;
  let last = null;

  const note = h("p", { class: "ctl__note", role: "status", hidden: true });
  const dock = h("section", { class: "dock", "aria-label": "Decisions waiting on you", hidden: true }, h("ol", { class: "dock__list" }), note);
  const list = dock.firstChild;
  const thread = h("ol", { class: "chat__thread", "aria-label": "Conversation with the company" });
  const runner = h("p", { class: "chat__runner" });
  const input = h("input", { class: "chat__input", type: "text", maxlength: 4000, "aria-label": "Message the company", placeholder: "Tell the company something, or ask for work…", autocomplete: "off" });
  const send = h("button", { class: "chat__send", type: "submit" }, "Send");
  const toggle = h("button", { class: "chat__toggle", type: "button", "aria-expanded": "false", "aria-label": "Show the conversation" }, h("span", { class: "chat__badge", hidden: true }));
  const form = h("form", { class: "chat__form" }, toggle, input, send);
  const sheetSwitch = presetSwitch();
  const sheet = h("div", { class: "chat__sheet", hidden: true }, h("div", { class: "chat__head" }, runner, sheetSwitch.el), thread);
  const chat = h("section", { class: "chat", "aria-label": "Chat with the company", hidden: true }, sheet, form);
  const headerSwitch = presetSwitch();
  headerSwitch.el.classList.add("top__preset");
  headerSwitch.el.hidden = true;

  const say = (text) => {
    note.textContent = text;
    note.hidden = !text;
  };

  async function post(action, body) {
    let res;
    try {
      res = await fetch(`/api/control/${action}${query}`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(body) });
    } catch {
      say("Could not reach the server. Nothing was recorded.");
      return false;
    }
    if (res.ok) {
      say("");
      return true;
    }
    let why = `The server refused it (${res.status}).`;
    try {
      why = (await res.json()).error || why;
    } catch { /* keep the status line */ }
    say(res.status === 403 ? "This page may not write. Open the link the server printed when it started." : why);
    return false;
  }

  function presetSwitch() {
    const buttons = new Map(PRESETS.map((p) => {
      const cost = h("small", {});
      const b = h("button", { type: "button", "data-preset": p, "aria-pressed": "false" }, p, cost);
      b.addEventListener("click", () => {
        if (b.getAttribute("aria-pressed") !== "true") post("preset", { name: p });
      });
      return [p, { b, cost }];
    }));
    const el = h("div", { class: "seg preset", role: "group", "aria-label": "Effort preset" }, [...buttons.values()].map((x) => x.b));
    return {
      el,
      update(control) {
        for (const [p, { b, cost }] of buttons) {
          b.setAttribute("aria-pressed", String(control.preset === p));
          const usd = (control.presets.find((x) => x.name === p) || {}).usd_per_item;
          cost.textContent = usd == null ? "" : ` $${usd < 10 ? usd.toFixed(1) : Math.round(usd)}`;
          b.title = usd == null ? "No measured runs on this preset yet" : `About $${usd.toFixed(2)} per verified item, from this project's runs`;
        }
      },
    };
  }

  // ---------- cards: patched by key, so a half-typed reason or answer survives a new snapshot
  function armed(button, label, act) {
    let timer = null;
    button.addEventListener("click", () => {
      if (!timer) {
        button.textContent = "Tap again to confirm";
        button.classList.add("is-armed");
        timer = setTimeout(() => {
          timer = null;
          button.textContent = label;
          button.classList.remove("is-armed");
        }, CONFIRM_MS);
        return;
      }
      clearTimeout(timer);
      timer = null;
      button.textContent = label;
      button.classList.remove("is-armed");
      act();
    });
  }

  function gateCard(w) {
    const body = { gate: w.gate };
    if (w.gate === "release") body.ref = w.ref;
    const approve = h("button", { class: "btn btn--go", type: "button" }, "Approve");
    const reject = h("button", { class: "btn", type: "button" }, "Reject");
    const reason = h("input", { class: "ctlcard__input", type: "text", maxlength: 4000, "aria-label": "Why reject it?", placeholder: "Why? The company reads this." });
    const confirm = h("button", { class: "btn btn--stop", type: "submit" }, "Reject");
    const why = h("form", { class: "ctlcard__form", hidden: true }, reason, confirm);
    armed(approve, "Approve", () => post("approve", body));
    reject.addEventListener("click", () => {
      why.hidden = !why.hidden;
      if (!why.hidden) reason.focus();
    });
    why.addEventListener("submit", (e) => {
      e.preventDefault();
      if (reason.value.trim()) post("reject", { ...body, reason: reason.value });
    });
    const title = h("p", { class: "ctlcard__title" });
    const link = w.gate === "release" ? h("a", { class: "ctlcard__link", href: `?view=work#${w.ref}` }, "See the item") : null;
    const el = h("li", { class: "ctlcard", "data-kind": "gate" }, h("p", { class: "ctlcard__kind" }, `${w.gate} gate`), title, link, h("div", { class: "ctlcard__actions" }, approve, reject), why);
    return { el, title };
  }

  function questionCard(w) {
    const answer = h("input", { class: "ctlcard__input", type: "text", maxlength: 4000, "aria-label": `Answer ${w.id}`, placeholder: "Your answer" });
    const reply = h("button", { class: "btn btn--go", type: "submit" }, "Answer");
    const form_ = h("form", { class: "ctlcard__form" }, answer, reply);
    form_.addEventListener("submit", (e) => {
      e.preventDefault();
      if (answer.value.trim()) post("answer", { qid: w.id, text: answer.value });
    });
    const title = h("p", { class: "ctlcard__title" });
    const el = h("li", { class: "ctlcard", "data-kind": "question" }, h("p", { class: "ctlcard__kind" }, `Question ${w.id}`), title, form_);
    return { el, title };
  }

  function renderCards(s) {
    const open = new Set(s.waiting.map((w) => w.key));
    for (const [key, card] of refs.cards) {
      if (!open.has(key)) {
        card.el.remove();
        refs.cards.delete(key);
      }
    }
    for (const w of s.waiting) {
      if (w.kind !== "gate" && w.kind !== "question") continue;
      let card = refs.cards.get(w.key);
      if (!card) {
        card = w.kind === "gate" ? gateCard(w) : questionCard(w);
        refs.cards.set(w.key, card);
        list.append(card.el);
      }
      if (card.title.textContent !== w.title) card.title.textContent = w.title;
    }
    dock.hidden = refs.cards.size === 0 && note.hidden;
  }

  // ---------- thread: the CEO's messages and the ledger events addressed to them
  function renderThread(s) {
    const c = s.control;
    const rows = c.messages.filter((m) => m.kind !== "preset").map((m) => ({ ts: m.ts, you: true, text: m.text, ack: m.ack, kind: m.kind }));
    for (const e of s.events) {
      if (!THREAD_EVENTS.test(e.event || "") || e.event === "message.acknowledged") continue;
      if (e.event === "question.asked" && (e.extra || {}).audience && e.extra.audience !== "ceo") continue;
      rows.push({ ts: e.ts, you: false, who: e.actor, text: `${e.event}: ${e.summary || ""}` });
    }
    rows.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0));
    const shown = rows.slice(-40);
    const sig = JSON.stringify(shown);
    if (sig === refs.threadSig) return;
    refs.threadSig = sig;
    const atEnd = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 40;
    thread.replaceChildren(...shown.map((r) => h("li", { class: `msg ${r.you ? "msg--you" : ""}` },
      h("p", { class: "msg__who" }, `${r.you ? "you" : r.who} · ${r.ts.slice(5, 16).replace("T", " ")}`),
      h("p", { class: "msg__text" }, r.text),
      r.you && r.kind === "message" ? h("p", { class: `msg__ack ${r.ack ? "" : "is-pending"}` }, r.ack ? `${r.ack.by}: ${r.ack.summary}` : "not read yet") : null)));
    if (atEnd) thread.scrollTop = thread.scrollHeight;
    const pending = c.messages.filter((m) => m.kind === "message" && !m.ack).length;
    toggle.firstChild.hidden = pending === 0;
    toggle.firstChild.textContent = String(pending);
  }

  function renderRunner(s) {
    const r = s.control.runner;
    runner.textContent = r.active ? `Runner: ${r.doing}` : "No runner. Decisions wait in the record until you start `tools/talos/talos work`.";
    runner.dataset.active = String(r.active);
  }

  // ---------- wiring
  toggle.addEventListener("click", () => {
    sheet.hidden = !sheet.hidden;
    toggle.setAttribute("aria-expanded", String(!sheet.hidden));
    toggle.setAttribute("aria-label", sheet.hidden ? "Show the conversation" : "Hide the conversation");
    if (!sheet.hidden) thread.scrollTop = thread.scrollHeight;
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value;
    if (!text.trim()) return;
    send.disabled = true;
    if (await post("say", { text })) input.value = "";
    send.disabled = false;
  });

  async function loadSession() {
    try {
      const res = await fetch(sessionUrl, { cache: "no-store", credentials: "same-origin" });
      session = res.ok ? await res.json() : { writable: false, authed: false };
    } catch {
      session = { writable: false, authed: false };
    }
    if (last) update(last);
  }

  function update(s) {
    last = s;
    if (!s.control) return false;
    if (session === null) {
      session = { pending: true };
      loadSession();
    }
    const on = Boolean(session.writable && session.authed);
    document.documentElement.classList.toggle("has-control", on);
    chat.hidden = !on;
    headerSwitch.el.hidden = !on;
    if (!on) {
      dock.hidden = true;
      return false;
    }
    headerSwitch.update(s.control);
    sheetSwitch.update(s.control);
    renderCards(s);
    renderThread(s);
    renderRunner(s);
    return true;
  }

  return { dock, chat, preset: headerSwitch.el, update };
}
