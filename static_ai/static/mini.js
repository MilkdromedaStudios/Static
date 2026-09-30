import { api, preview, setToken } from "./api.js";
import {
  $,
  el,
  button,
  hydrateIcons,
  markdown,
  downloadBlob,
  money,
  toast,
} from "./ui.js";

let conversation = null,
  run = null,
  timer = null,
  busy = false;
const active = ["queued", "running", "awaiting_approval"];
hydrateIcons();
function stored(value) {
  try {
    if (value !== undefined)
      localStorage.setItem("static-mini-conversation", value || "");
    else return localStorage.getItem("static-mini-conversation");
  } catch {}
}
function controls() {
  $("#mini-send").disabled = busy;
  $("#mini-new").disabled = busy;
  $("#mini-stop").hidden = !busy;
  $("#mini-mode").disabled = busy;
}
function status(text) {
  $("#mini-status").textContent = text;
}
function openLink() {
  $("#mini-open").href =
    "./chat.html" +
    (conversation ? "?id=" + encodeURIComponent(conversation) : "");
}
async function download(id, name) {
  try {
    downloadBlob(
      await api("/api/artifacts/" + id + "/download", { blob: true }),
      name,
    );
  } catch (e) {
    toast(e.message, true);
  }
}
function paint(messages) {
  const list = $("#mini-messages"),
    nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 90;
  list.replaceChildren();
  if (!messages.length) {
    const empty = el("div", "mini-empty");
    empty.append(
      el("h1", "", "A small window. A little help."),
      el(
        "p",
        "",
        preview
          ? "Try an example chat. This preview uses sample replies and makes no AI calls."
          : "Ask a question, make a plan, or pick up where you left off.",
      ),
    );
    list.append(empty);
  }
  for (const message of messages.filter((m) =>
    ["user", "assistant"].includes(m.role),
  )) {
    const row = el("article", "mini-message " + message.role);
    row.append(
      el("div", "mini-role", message.role === "user" ? "You" : "Static"),
      markdown(message.content, download),
    );
    list.append(row);
  }
  if (nearBottom) list.scrollTop = list.scrollHeight;
}
async function refresh() {
  clearTimeout(timer);
  if (!conversation) {
    paint([]);
    return;
  }
  try {
    const data = await api("/api/conversations/" + conversation);
    paint(data.messages);
    run = data.runs.find((r) => active.includes(r.status))?.id || null;
    busy = Boolean(run);
    controls();
    $("#mini-approvals").replaceChildren();
    if (run) {
      const result = await api("/api/runs/" + run);
      status(
        result.status === "awaiting_approval"
          ? "Review the action before Static continues."
          : "Static is working… " + money(result.spent),
      );
      for (const approval of result.approvals) {
        const card = el("div", "mini-approval");
        card.append(
          el("strong", "", "Action needs approval"),
          el("p", "", "Review in the full workspace for action details."),
        );
        // Approval details remain in the full workspace; this small view never hides a charge.
        const link = el("a", "button", "Review action");
        link.href = $("#mini-open").href;
        card.append(
          link,
          button("Decline", async () => {
            await api("/api/approvals/" + approval.id, {
              method: "POST",
              body: { allow: false },
            });
            await refresh();
          }),
        );
        $("#mini-approvals").append(card);
      }
      timer = setTimeout(refresh, 800);
    } else {
      const last = data.runs[0];
      status(
        last?.error ||
          (last?.status === "failed"
            ? "Run failed. Open the workspace for details."
            : "Quick chat. Same saved workspace."),
      );
    }
  } catch (e) {
    if (e.status === 404) {
      conversation = null;
      stored("");
      paint([]);
    } else {
      status(e.message);
      timer = setTimeout(refresh, 2500);
    }
  }
  openLink();
}
$("#mini-compose").onsubmit = async (event) => {
  event.preventDefault();
  if (busy || !$("#mini-prompt").value.trim()) return;
  busy = true;
  controls();
  try {
    if (!conversation) {
      conversation = (
        await api("/api/conversations", { method: "POST", body: {} })
      ).id;
      stored(conversation);
      openLink();
    }
    run = (
      await api("/api/conversations/" + conversation + "/chat", {
        method: "POST",
        body: { message: $("#mini-prompt").value, mode: $("#mini-mode").value },
      })
    ).id;
    $("#mini-prompt").value = "";
    await refresh();
  } catch (e) {
    busy = false;
    controls();
    status(e.message);
    toast(e.message, true);
  }
};
$("#mini-new").onclick = () => {
  if (busy) return;
  conversation = null;
  run = null;
  clearTimeout(timer);
  stored("");
  openLink();
  paint([]);
  status("New quick chat.");
  $("#mini-prompt").focus();
};
$("#mini-stop").onclick = async () => {
  try {
    if (run) await api("/api/runs/" + run + "/stop", { method: "POST" });
    await refresh();
  } catch (e) {
    toast(e.message, true);
  }
};
$("#mini-theme").onclick = () =>
  window.staticTheme.set(
    document.documentElement.dataset.theme === "dark" ? "light" : "dark",
  );
$("#mini-prompt").onkeydown = (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    $("#mini-compose").requestSubmit();
  }
};
$("#mini-unlock").onsubmit = async (event) => {
  event.preventDefault();
  setToken($("#mini-token").value);
  $("#mini-token").value = "";
  await initialize();
};
async function initialize() {
  try {
    const settings = await api("/api/settings");
    $("#mini-unlock").hidden = true;
    $("#mini-compose").hidden = false;
    $("#mini-model").textContent =
      (preview ? "Sample preview · " : "") +
      settings.settings.models.map((m) => m.name).join(" / ") +
      " · run limit " +
      money(settings.settings.run_budget_usd);
    conversation =
      new URL(location.href).searchParams.get("id") || stored() || null;
    openLink();
    await refresh();
  } catch (e) {
    status(e.message);
    if (e.status === 401) {
      $("#mini-unlock").hidden = false;
      $("#mini-compose").hidden = true;
    }
  }
}
initialize();
