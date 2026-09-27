export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [
  ...root.querySelectorAll(selector),
];
export function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}
const paths = {
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
  "check-square":
    '<rect x="3" y="3" width="18" height="18" rx="5"/><path d="m7 12 3 3 7-7"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  sparkles:
    '<path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6Z"/>',
  folder:
    '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  plug: '<path d="M8 3v5m8-5v5M6 8h12v4a6 6 0 0 1-12 0ZM12 18v4"/>',
  settings:
    '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  moon: '<path d="M20.7 13A9 9 0 0 1 11 3.3 9 9 0 1 0 20.7 13Z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  leaf: '<path d="M20 4C5 2 2 12 7 17s16 2 13-13ZM5 20 15 9"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  "arrow-up": '<path d="M12 19V5m-6 6 6-6 6 6"/>',
  chevron: '<path d="m8 5 7 7-7 7"/>',
  down: '<path d="m6 9 6 6 6-6"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a20 20 0 0 1 0 18 20 20 0 0 1 0-18Z"/>',
  paperclip:
    '<path d="m9 13 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l8-8a2 2 0 0 1 3 3l-8 8"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  file: '<path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8M8 16h6"/>',
  image:
    '<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-7 5 7"/>',
  video:
    '<rect x="3" y="5" width="18" height="14" rx="4"/><path d="m10 9 5 3-5 3Z"/>',
  cube: '<path d="m12 3 9 5v9l-9 5-9-5V8Zm0 9 9-4m-9 4L3 8m9 4v10M7.5 5.5l9 5"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  chat: '<path d="M21 11a8 8 0 0 1-8 8H7l-4 3V11a9 9 0 0 1 18 0Z"/><path d="M7 10h10M7 14h6"/>',
  bag: '<path d="M5 7h14l2 14H3ZM8 8V6a4 4 0 0 1 8 0v2"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-3 5-5 3 3-5Z"/>',
  book: '<path d="M12 5Q6 1 3 4v16q4-3 9 0 5-3 9 0V4q-3-3-9 1Zm0 0v15"/>',
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18M7 15h3m4 0h3"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m3 6 9 7 9-7"/>',
  chart: '<path d="M4 3v18h17M8 17v-5m5 5V7m5 10V4"/>',
  bolt: '<path d="m13 2-9 12h7l-1 8 10-13h-7Z"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/>',
  github:
    '<path d="M9 20C3 22 3 17 1 17m16 4v-4a4 4 0 0 0-1-3c3-.3 6-1.5 6-6a5 5 0 0 0-1-3 5 5 0 0 0-.1-3S20 1.7 17 3a12 12 0 0 0-6 0C8 1.7 7.1 2 7.1 2A5 5 0 0 0 7 5a5 5 0 0 0-1 3c0 4.5 3 5.7 6 6a4 4 0 0 0-1 3v4"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 10-8 10S4 17 4 12V6Zm-4 9 3 3 5-6"/>',
  refresh:
    '<path d="M21 4v6h-6M3 20v-6h6M5 8a8 8 0 0 1 13-3l3 5M3 14l3 5a8 8 0 0 0 13-3"/>',
  edit: '<path d="m14 4 6 6M3 21l6-1L21 8a2 2 0 0 0-6-6L3 14Z"/>',
  trash: '<path d="M3 6h18M8 6V3h8v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
};
export function icon(name, className = "") {
  const wrapper = el("span", "icon " + className);
  // Only fixed, application-owned SVG paths are inserted here. User text never becomes markup.
  wrapper.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.sparkles}</svg>`;
  return wrapper;
}
export function hydrateIcons(root = document) {
  $$("[data-icon]", root).forEach((n) => n.replaceWith(icon(n.dataset.icon)));
}
export function button(label, action, className = "button", iconName) {
  const b = el("button", className);
  b.type = "button";
  if (iconName) b.append(icon(iconName));
  b.append(document.createTextNode(label));
  b.addEventListener("click", async () => {
    try {
      await action(b);
    } catch (e) {
      toast(e.message, true);
    }
  });
  return b;
}
let toastTimer;
export function toast(message, error = false) {
  const n = $("#toast");
  n.textContent = message;
  n.className = "show" + (error ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (n.className = ""), 5500);
}
export function field(label, value = "", type = "text", options = {}) {
  const wrap = el("label", "field");
  wrap.append(el("span", "", label));
  const input = el(type === "textarea" ? "textarea" : "input");
  if (type !== "textarea") input.type = type;
  input.value = value ?? "";
  Object.assign(input, options);
  wrap.append(input);
  return { wrap, input };
}
export function selectField(label, choices, value) {
  const wrap = el("label", "field");
  wrap.append(el("span", "", label));
  const input = el("select");
  for (const [v, text] of choices) {
    const option = el("option", "", text);
    option.value = v;
    input.append(option);
  }
  input.value = value;
  wrap.append(input);
  return { wrap, input };
}
export function badge(text, tone = "") {
  return el("span", "badge " + tone, text);
}
export function empty(title, subtitle, action) {
  const node = el("div", "empty-state");
  node.append(icon("sparkles"), el("h3", "", title), el("p", "", subtitle));
  if (action) node.append(action);
  return node;
}
export const money = (v) => "$" + Number(v || 0).toFixed(2);
export function relativeDate(value) {
  const days = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 86400000),
  );
  return days === 0 ? "Today" : days === 1 ? "Yesterday" : days + " days ago";
}
export function safeURL(value) {
  if (/^\/api\/artifacts\/[a-f0-9]{32}\/download$/.test(value)) return value;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
export function markdown(text, onDownload) {
  const root = el("div", "markdown");
  let code = null;
  const inline = (node, str) => {
    const tokens = /(\[[^\]\n]+\]\([^)\s]+\)|\*\*[^*]+\*\*|`[^`]+`)/g;
    let cursor = 0;
    for (const match of str.matchAll(tokens)) {
      node.append(document.createTextNode(str.slice(cursor, match.index)));
      const value = match[0];
      if (value.startsWith("[")) {
        const [, label, raw] = value.match(/^\[([^\]]+)\]\((.+)\)$/);
        const url = safeURL(raw);
        if (url) {
          const link = el("a", "", label);
          link.href = url;
          if (url.startsWith("/api/artifacts/"))
            link.onclick = (e) => {
              e.preventDefault();
              onDownload(url.split("/")[3], label);
            };
          else {
            link.target = "_blank";
            link.rel = "noopener noreferrer";
          }
          node.append(link);
        } else node.append(document.createTextNode(label));
      } else
        node.append(
          el(
            value.startsWith("`") ? "code" : "strong",
            "",
            value.slice(
              value.startsWith("`") ? 1 : 2,
              value.startsWith("`") ? -1 : -2,
            ),
          ),
        );
      cursor = match.index + value.length;
    }
    node.append(document.createTextNode(str.slice(cursor)));
  };
  for (const line of String(text).split("\n")) {
    if (line.startsWith("```")) {
      if (code) code = null;
      else {
        code = el("pre");
        root.append(code);
      }
      continue;
    }
    if (code) {
      code.textContent += line + "\n";
      continue;
    }
    if (!line.trim()) continue;
    const heading = line.match(/^(#{1,3}) (.+)$/);
    const list = line.match(/^(?:[-*]|\d+\.) (.+)$/);
    const row = el(
      heading ? "h" + (heading[1].length + 2) : "p",
      list ? "list-line" : "",
    );
    inline(row, heading ? heading[2] : list ? "• " + list[1] : line);
    root.append(row);
  }
  return root;
}
export function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = el("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
