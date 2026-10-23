// DigitBox AI for the standalone web preview. GitHub Pages can't run the
// Python app or hold API keys, so a connected DigitBox account answers for
// real: free accounts get a few messages a day with Nemotron, DigitBox Pro is
// unlimited and adds a stronger model. The keys stay on DigitBox's server.
// The Python app never loads this module.
const config =
  window.STATIC_RUNTIME?.mode === "preview" ? window.STATIC_RUNTIME.ai : null;
const KEY = "static-digitbox-ai-v1";
export const hostedAvailable = Boolean(config?.api && config?.connect);
let status = null;

function read() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "null") || {};
  } catch {
    return {};
  }
}
function write(value) {
  try {
    if (value) localStorage.setItem(KEY, JSON.stringify(value));
    else localStorage.removeItem(KEY);
  } catch {}
}
function changed() {
  window.dispatchEvent(new Event("static-hosted"));
}
// /ai/connect on DigitBox returns here with an AI-only token in the fragment.
if (hostedAvailable) {
  const match = /^#digitbox-ai=([A-Za-z0-9_%-]{8,200})$/.exec(location.hash);
  if (match) {
    write({ ...read(), token: decodeURIComponent(match[1]) });
    history.replaceState(
      history.state,
      "",
      location.pathname + location.search,
    );
  }
  window.addEventListener("storage", (e) => {
    if (e.key !== KEY) return;
    status = null;
    changed();
  });
}
function token() {
  return hostedAvailable ? read().token || "" : "";
}
export function connected() {
  return Boolean(token());
}
export function connectURL() {
  const back = new URL(location.href);
  back.hash = "";
  const url = new URL(config.connect);
  url.searchParams.set("origin", location.origin);
  url.searchParams.set("return", back.href);
  return url.href;
}
export function upgradeURL() {
  return config?.upgrade || "https://digitbox.dev/profile#digitbox-pro";
}
function forget() {
  const { token: _, ...rest } = read();
  write(Object.keys(rest).length ? rest : null);
  status = null;
  changed();
}
// The models and free allowance, for explaining the plans before connecting.
export async function publicStatus() {
  const response = await fetch(config.api + "/status");
  const body = await response.json().catch(() => ({}));
  if (!body.models) throw Error(body.error || "DigitBox AI is unavailable.");
  return body;
}
// The plan, models and today's allowance; null when not connected.
export async function hostedStatus(refresh = false) {
  if (!connected()) return null;
  if (status && !refresh) return status;
  let response;
  try {
    response = await fetch(config.api + "/status", {
      headers: { Authorization: "Bearer " + token() },
    });
  } catch {
    throw Error("Cannot reach DigitBox AI. Check your connection, then retry.");
  }
  const body = await response.json().catch(() => ({}));
  if (body.tokenInvalid) {
    forget();
    return null;
  }
  if (!response.ok && !body.models)
    throw Error(body.error || "DigitBox AI is unavailable right now.");
  status = body;
  changed();
  return body;
}
export function cachedStatus() {
  return status;
}
export async function disconnect() {
  const current = token();
  forget();
  if (current)
    await fetch(config.api + "/connect", {
      method: "DELETE",
      headers: { Authorization: "Bearer " + current },
    }).catch(() => {});
}
export function chosenModel() {
  const id = read().model || "";
  const models = status?.models || [];
  const usable = (m) => m && !m.locked && m.configured;
  if (usable(models.find((m) => m.id === id))) return id;
  return status?.defaultModel || models.find(usable)?.id || "";
}
export function chooseModel(id) {
  write({ ...read(), model: id });
}
export function planLabel(s = status) {
  if (!s?.signedIn) return "";
  if (s.plan === "pro") return "Pro · Unlimited";
  const left = s.usage?.remaining ?? s.freeDailyLimit;
  return (
    "Free · " + left + (left === 1 ? " message" : " messages") + " left today"
  );
}
// Streams a reply; onText receives the reply so far. Resolves to
// { text, model, remaining }. Errors carry .code from DigitBox AI.
export async function hostedChat({ messages, model, context, signal, onText }) {
  let response;
  try {
    response = await fetch(config.api + "/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token(),
      },
      body: JSON.stringify({ messages, model, context, surface: "static" }),
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw Error("Cannot reach DigitBox AI. Check your connection, then retry.");
  }
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    if (response.status === 401) forget();
    const error = Error(
      body.error || "DigitBox AI request failed (" + response.status + ").",
    );
    error.code = body.code || "";
    throw error;
  }
  const remaining = response.headers.get("X-AI-Remaining");
  const result = {
    text: "",
    model: response.headers.get("X-AI-Model") || "",
    remaining:
      remaining && remaining !== "unlimited" ? Number(remaining) : null,
  };
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (let done = false; !done; ) {
    const chunk = await reader.read();
    done = chunk.done;
    buffer += decoder.decode(chunk.value || new Uint8Array(), {
      stream: !done,
    });
    const lines = buffer.split("\n");
    buffer = done ? "" : lines.pop();
    for (const line of lines) {
      const data = line.trim().replace(/^data:\s*/, "");
      if (!line.trim().startsWith("data:") || !data) continue;
      if (data === "[DONE]") {
        done = true;
        break;
      }
      let event;
      try {
        event = JSON.parse(data);
      } catch {
        continue;
      }
      if (event.error) {
        const error = Error(
          event.error.message || "The model stopped with an error.",
        );
        error.partial = result.text;
        throw error;
      }
      const piece = event.choices?.[0]?.delta?.content;
      if (piece) {
        result.text += piece;
        onText?.(result.text);
      }
    }
  }
  if (status?.usage && result.remaining !== null) {
    status.usage.remaining = result.remaining;
    changed();
  }
  if (!result.text.trim())
    throw Error("The model sent an empty reply. Try again or rephrase.");
  return result;
}
const types = {
  md: "text/markdown",
  txt: "text/plain",
  csv: "text/csv",
  tsv: "text/tab-separated-values",
  json: "application/json",
  html: "text/html",
  css: "text/css",
  js: "text/javascript",
  py: "text/x-python",
  xml: "application/xml",
  yaml: "text/yaml",
  yml: "text/yaml",
  svg: "image/svg+xml",
  obj: "text/plain",
  ics: "text/calendar",
  eml: "message/rfc822",
};
// ```lang file=name.ext blocks become files; save(name, mime, content)
// returns the replacement text (a download link) for each one.
export function extractFiles(text, save) {
  return text.replace(
    /```[\w.+-]*[ \t]+file(?:name)?=["']?([^\s"'`]+)["']?[^\n]*\n([\s\S]*?)\n```/g,
    (block, raw, content) => {
      const name = raw
        .split(/[\\/]/)
        .pop()
        .replace(/[^\w.\- ]+/g, "_")
        .replace(/^\.+/, "")
        .slice(0, 80);
      const mime = types[name.split(".").pop().toLowerCase()];
      return name.includes(".") && mime ? save(name, mime, content) : block;
    },
  );
}
