export const preview = window.STATIC_RUNTIME?.mode === "preview";
let token;
try {
  token = sessionStorage.getItem("static-token") || "";
} catch {
  token = "";
}
export function setToken(value) {
  token = value;
  try {
    sessionStorage.setItem("static-token", value);
  } catch {}
}
export async function api(path, { method = "GET", body, blob = false } = {}) {
  if (preview) {
    const { demoRequest } = await import("./demo.js");
    return demoRequest(path, method, body);
  }
  const headers = { "X-Static-Client": "web" };
  if (token) headers.Authorization = "Bearer " + token;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, { method, headers, body });
  } catch {
    throw Error(
      "Cannot reach Static. Check that the Python server is running, then retry.",
    );
  }
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = "The request failed.";
    }
    const message = Array.isArray(detail)
      ? detail.map((x) => x.loc.slice(1).join(".") + ": " + x.msg).join("; ")
      : detail;
    const error = new Error(message || "Request failed");
    error.status = response.status;
    throw error;
  }
  return blob ? response.blob() : response.json();
}
