// dom.js: the only file that creates DOM from data (ADR-0005 point 2). Text goes in as text nodes, never as markup.
const SVG_NS = "http://www.w3.org/2000/svg";

function fill(el, attrs, children) {
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    el.setAttribute(name, value === true ? "" : String(value));
  }
  for (const child of children) append(el, child);
  return el;
}

function append(el, child) {
  if (child === null || child === undefined || child === false) return;
  if (Array.isArray(child)) {
    for (const c of child) append(el, c);
  } else if (child instanceof Node) {
    el.append(child);
  } else {
    el.append(String(child));
  }
}

export function h(tag, attrs = {}, ...children) {
  return fill(document.createElement(tag), attrs, children);
}

export function svg(tag, attrs = {}, ...children) {
  return fill(document.createElementNS(SVG_NS, tag), attrs, children);
}

export function text(node, s) {
  node.textContent = String(s);
}

export function keyed(parent, key) {
  return parent.querySelector(`:scope > [data-key="${CSS.escape(String(key))}"]`);
}
