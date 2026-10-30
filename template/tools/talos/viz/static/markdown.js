// markdown.js: the ADR-0005 point 5 subset, parsed into DOM nodes built only with the caller's h().
// Never markup: text always goes in as text nodes, so raw HTML in a report is shown literally.
// Anything outside the subset (images, quotes, rules, deeper headings, other URL schemes) is literal text.

const NUM = /^[\d.,%$]+[kKM]?$/;
const FENCE = /^```([^\s`]*)\s*$/;
const HEADING = /^(#{1,4}) +(\S.*?)\s*#*\s*$/;
const ITEM = /^(\s*)([-*]|\d+\.) +(.*)$/;
const SEPARATOR = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;
const LINK = /^\[([^\]]+)\]\(([^)\s]+)\)/;
const SAFE_HREF = /^(https?:\/\/|#)/;

function inline(src, h, links = true) {
  const out = [];
  let buf = "";
  const flush = () => {
    if (buf) out.push(buf);
    buf = "";
  };
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    const rest = src.slice(i);
    if (c === "`") {
      const end = src.indexOf("`", i + 1);
      if (end > i + 1) {
        flush();
        out.push(h("code", {}, src.slice(i + 1, end)));
        i = end + 1;
        continue;
      }
    } else if (c === "*" && src.startsWith("**", i)) {
      const end = src.indexOf("**", i + 2);
      if (end > i + 2) {
        flush();
        out.push(h("strong", {}, inline(src.slice(i + 2, end), h, links)));
        i = end + 2;
        continue;
      }
    } else if (c === "_" && (i === 0 || /[^\w]/.test(src[i - 1])) && i + 1 < src.length && !/\s/.test(src[i + 1])) {
      let end = i + 1;
      let found = -1;
      while ((end = src.indexOf("_", end)) !== -1) {
        if (end > i + 1 && !/\s/.test(src[end - 1]) && (end + 1 === src.length || /[^\w]/.test(src[end + 1]))) {
          found = end;
          break;
        }
        end += 1;
      }
      if (found > 0) {
        flush();
        out.push(h("em", {}, inline(src.slice(i + 1, found), h, links)));
        i = found + 1;
        continue;
      }
    } else if (c === "!" && src[i + 1] === "[") {
      const m = LINK.exec(src.slice(i + 1));
      if (m) {
        buf += `!${m[0]}`; // images are not in the subset
        i += 1 + m[0].length;
        continue;
      }
    } else if (c === "[") {
      const m = LINK.exec(rest);
      if (m) {
        if (links && SAFE_HREF.test(m[2])) {
          flush();
          const attrs = { href: m[2] };
          if (!m[2].startsWith("#")) {
            attrs.rel = "noopener";
            attrs.target = "_blank";
          }
          out.push(h("a", attrs, inline(m[1], h, false)));
        } else {
          buf += m[0];
        }
        i += m[0].length;
        continue;
      }
    }
    buf += c;
    i += 1;
  }
  flush();
  return out;
}

function cells(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
  return s.split(/(?<!\\)\|/).map((c) => c.replace(/\\\|/g, "|").trim());
}

function startsBlock(line, next) {
  return FENCE.test(line) || HEADING.test(line) || ITEM.test(line) || (line.includes("|") && next !== undefined && SEPARATOR.test(next) && next.includes("-") && line.includes("|"));
}

export function render(markdown, h) {
  const frag = document.createDocumentFragment();
  const lines = String(markdown ?? "").replace(/\r\n?/g, "\n").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    let m = FENCE.exec(line);
    if (m) {
      const body = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) body.push(lines[i++]);
      i += 1;
      frag.append(h("pre", {}, h("code", { "data-lang": m[1] || null }, body.join("\n"))));
      continue;
    }
    m = HEADING.exec(line);
    if (m) {
      frag.append(h(`h${m[1].length + 1}`, {}, inline(m[2], h)));
      i += 1;
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length && SEPARATOR.test(lines[i + 1]) && lines[i + 1].includes("|")) {
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) rows.push(cells(lines[i++]));
      frag.append(h("table", {},
        h("thead", {}, h("tr", {}, head.map((t) => h("th", { scope: "col" }, inline(t, h))))),
        h("tbody", {}, rows.map((r) => h("tr", {}, head.map((label, k) => {
          const t = r[k] ?? "";
          return h("td", { "data-label": label || "Value", class: NUM.test(t) ? "num" : null }, inline(t, h));
        }))))));
      continue;
    }
    if (ITEM.test(line)) {
      i = list(lines, i, h, frag);
      continue;
    }
    const para = [line.trim()];
    i += 1;
    while (i < lines.length && lines[i].trim() && !startsBlock(lines[i], lines[i + 1])) para.push(lines[i++].trim());
    frag.append(h("p", {}, inline(para.join(" "), h)));
  }
  return frag;
}

// A list block with nesting by indentation. Returns the index of the first line after it.
function list(lines, start, h, frag) {
  const stack = [];
  let i = start;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) break;
    const m = ITEM.exec(line.replace(/\t/g, "    "));
    if (!m) {
      // an indented line that is not a marker continues the last item; anything else ends the list
      if (!stack.length || !/^\s+\S/.test(line)) break;
      stack[stack.length - 1].last.append(" ", ...inline(line.trim(), h));
      i += 1;
      continue;
    }
    const indent = m[1].length;
    while (stack.length && stack[stack.length - 1].indent > indent) stack.pop();
    let top = stack[stack.length - 1];
    if (!top || top.indent < indent) {
      const el = h(/\d/.test(m[2]) ? "ol" : "ul", {});
      if (top) (top.last || top.el).append(el);
      else frag.append(el);
      top = { indent, el, last: null };
      stack.push(top);
    }
    const li = h("li", {}, inline(m[3], h));
    top.el.append(li);
    top.last = li;
    i += 1;
  }
  return i;
}
