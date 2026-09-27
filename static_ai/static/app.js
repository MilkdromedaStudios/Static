import {
  $,
  $$,
  el,
  icon,
  hydrateIcons,
  button,
  toast,
  field,
  selectField,
  badge,
  empty,
  money,
  relativeDate,
  markdown,
  downloadBlob,
} from "./ui.js";
import { api, preview, setToken } from "./api.js";
import { ideas, creationTypes, skillInfo } from "./catalog.js";

const state = {
  settings: null,
  keys: {},
  spent: 0,
  conversations: [],
  tasks: [],
  page: "home",
  conv: null,
  run: null,
  after: 0,
  poll: null,
  generation: 0,
  attachments: [],
  busy: false,
  taskFilter: "all",
  taskQuery: "",
  fileFilter: "all",
  skillFilter: "all",
  createType: "document",
};
const labels = {
  home: "Home",
  chat: "Conversation",
  tasks: "Tasks",
  create: "Create",
  library: "Library",
  skills: "Skills",
  connections: "Connections",
  settings: "Settings",
};
const activeStatuses = ["queued", "running", "awaiting_approval"];
const categoryIcons = {
  work: "file",
  life: "calendar",
  research: "globe",
  creative: "sparkles",
};
const main = $("#main");
const modal = $("#modal");
function showModal(title, content) {
  $("#modal-title").textContent = title;
  $("#modal-content").replaceChildren(content);
  if (!modal.open) modal.showModal();
}
function closeModal() {
  modal.close();
}
$("#modal-close").onclick = closeModal;
modal.addEventListener("click", (e) => {
  if (e.target === modal) {
    const r = modal.getBoundingClientRect();
    if (
      e.clientX < r.left ||
      e.clientX > r.right ||
      e.clientY < r.top ||
      e.clientY > r.bottom
    )
      closeModal();
  }
});
function notice(text, tone = "") {
  const n = el("div", "notice " + tone);
  n.append(
    icon(tone === "error" ? "shield" : "sparkles"),
    el("span", "", text),
  );
  return n;
}
function heading(title, subtitle, action) {
  const h = el("div", "page-heading");
  const copy = el("div");
  copy.append(el("h1", "", title), el("p", "", subtitle));
  h.append(copy);
  if (action) h.append(action);
  return h;
}
function section(title, action) {
  const h = el("div", "section-heading");
  h.append(el("h2", "", title));
  if (action) h.append(action);
  return h;
}
function panelHeading(title, subtitle) {
  const h = el("div", "panel-heading"),
    c = el("div");
  c.append(el("h2", "", title));
  if (subtitle) c.append(el("p", "", subtitle));
  h.append(c);
  return h;
}
function art(kind) {
  const a = el("div", "idea-art art-" + kind);
  a.setAttribute("aria-hidden", "true");
  const shape = el(
    "div",
    { research: "orb", create: "sculpture", plan: "ticket", doc: "paper" }[
      kind
    ] || "orb",
  );
  if (kind === "plan" || kind === "doc")
    for (let i = 0; i < 3; i++) shape.append(el("span"));
  a.append(shape);
  return a;
}
function setMenu(open) {
  $("#sidebar").classList.toggle("open", open);
  $("#sidebar-shade").hidden = !open;
  $("#menu").setAttribute("aria-expanded", String(open));
}
$("#menu").onclick = () => setMenu(!$("#sidebar").classList.contains("open"));
$("#sidebar-shade").onclick = () => setMenu(false);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") setMenu(false);
  if ((e.metaKey || e.ctrlKey) && e.key === "k") {
    e.preventDefault();
    openSearch();
  }
  if (
    e.key === "n" &&
    !e.metaKey &&
    !e.ctrlKey &&
    !e.altKey &&
    !modal.open &&
    !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName)
  ) {
    e.preventDefault();
    newChat();
  }
});
function themeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  $("#theme-toggle").replaceChildren(icon(dark ? "sun" : "moon"));
  $("#theme-toggle").setAttribute(
    "aria-label",
    dark ? "Switch to light mode" : "Switch to dark mode",
  );
}
$("#theme-toggle").onclick = () => {
  window.staticTheme.set(
    document.documentElement.dataset.theme === "dark" ? "light" : "dark",
  );
  if (state.page === "settings") renderSettings();
};
window.addEventListener("static-theme", themeButton);
function pathFor(page) {
  return "./" + (page === "home" ? "index" : page) + ".html";
}
async function navigate(page, params = {}, push = true) {
  if (!labels[page]) page = "home";
  const url = new URL(pathFor(page), location.href);
  for (const [key, value] of Object.entries(params))
    if (value) url.searchParams.set(key, value);
  if (push) history.pushState({}, "", url);
  setMenu(false);
  await renderPage(page);
  main.focus({ preventScroll: true });
  window.scrollTo(0, 0);
}
async function route() {
  const file = location.pathname.split("/").pop().replace(".html", "");
  return renderPage(file === "index" || !file ? "home" : file);
}
document.addEventListener("click", (e) => {
  const link = e.target.closest("a[data-page]");
  if (!link || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  navigate(link.dataset.page).catch(fatal);
});
window.addEventListener("popstate", () => route().catch(fatal));
function updateShell() {
  const settings = state.settings;
  if (!settings) return;
  $("#profile-name").textContent =
    settings.display_name || "Personal workspace";
  $("#avatar").textContent = (settings.display_name || "S")
    .slice(0, 1)
    .toUpperCase();
  $("#task-count").textContent = state.tasks.filter(
    (t) => t.status !== "done",
  ).length;
  const allLocal = settings.models.every((m) => m.local);
  $("#connection-label").textContent = allLocal
    ? "Local first. More possible."
    : "A little help, on your terms.";
  $("#budget-label").textContent = preview
    ? "Example workspace · No charges"
    : money(state.spent) +
      " of " +
      money(settings.daily_budget_usd) +
      " daily budget";
  const recents = $("#recent");
  recents.replaceChildren();
  state.conversations
    .slice(0, 6)
    .forEach((c) =>
      recents.append(button(c.title, () => navigate("chat", { id: c.id }), "")),
    );
  if (!state.conversations.length)
    recents.append(el("p", "", "Your next idea starts here."));
}
async function refreshData() {
  const [config, conversations, tasks] = await Promise.all([
    api("/api/settings"),
    api("/api/conversations"),
    api("/api/tasks"),
  ]);
  state.settings = config.settings;
  state.keys = config.keys;
  state.spent = config.spent_today || 0;
  state.conversations = conversations;
  state.tasks = tasks;
  updateShell();
}
async function saveSettings(settings, message = "Settings saved") {
  const saved = await api("/api/settings", { method: "PUT", body: settings });
  state.settings = saved.settings;
  state.keys = saved.keys;
  updateShell();
  if (message) toast(preview ? message + " in this browser" : message);
}
function fatal(error) {
  if (error.status === 401) return unlock();
  main.replaceChildren(
    notice(error.message, "error"),
    button("Try again", () => init(), "button primary", "refresh"),
  );
}
function unlock() {
  const form = el("form");
  form.append(
    el(
      "p",
      "muted",
      "Enter the access token configured on your Static server. It stays in this browser session.",
    ),
  );
  const token = field("Workspace access token", "", "password", {
    required: true,
    autocomplete: "current-password",
  });
  form.append(token.wrap);
  const submit = el("button", "button primary", "Unlock workspace");
  submit.type = "submit";
  form.append(submit);
  form.onsubmit = async (e) => {
    e.preventDefault();
    setToken(token.input.value);
    submit.disabled = true;
    try {
      await refreshData();
      closeModal();
      await route();
    } catch (error) {
      toast(error.message, true);
    } finally {
      submit.disabled = false;
    }
  };
  showModal("Welcome to Static", form);
}
async function renderPage(page) {
  if (!labels[page]) page = "home";
  state.page = page;
  state.generation++;
  clearTimeout(state.poll);
  state.poll = null;
  state.run = null;
  state.after = 0;
  document.title = labels[page] + " · Static";
  $("#page-label").textContent = labels[page];
  $$("nav a").forEach((a) => {
    const current = a.dataset.page === page;
    a.classList.toggle("active", current);
    if (current) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  main.replaceChildren();
  const generation = state.generation;
  try {
    if (!state.settings) await refreshData();
    if (generation !== state.generation) return;
    await {
      home: renderHome,
      chat: renderChat,
      tasks: renderTasks,
      create: renderCreate,
      library: renderLibrary,
      skills: renderSkills,
      connections: renderConnections,
      settings: renderSettings,
    }[page]();
  } catch (error) {
    if (generation === state.generation) fatal(error);
  }
}
async function newChat() {
  state.conv = null;
  state.attachments = [];
  await navigate("chat");
  $("#prompt")?.focus();
}
$("#new-chat").onclick = () => newChat().catch(fatal);
async function usePrompt(prompt) {
  state.conv = null;
  state.attachments = [];
  await navigate("chat");
  $("#prompt").value = prompt;
  $("#prompt").focus();
}
function composer({ home = false } = {}) {
  const wrap = el("div", home ? "" : "chat-composer-wrap"),
    form = el("form", "composer");
  form.id = "composer";
  const input = el("textarea");
  input.id = "prompt";
  input.placeholder = home
    ? "What would you like a hand with?"
    : "Ask a follow-up, or give Static something to do…";
  input.setAttribute("aria-label", "Message Static");
  input.rows = home ? 3 : 2;
  input.maxLength = 16000;
  input.required = true;
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
  const attachments = el("div", "attachments");
  attachments.id = "attachments";
  const bottom = el("div", "composer-bottom"),
    tools = el("div", "composer-tools");
  const attach = button(
    "",
    () => $("#upload").click(),
    "icon-button",
    "paperclip",
  );
  attach.setAttribute("aria-label", "Attach a file");
  const mode = el("select", "mode-select");
  mode.id = "mode";
  mode.setAttribute("aria-label", "Model routing mode");
  [
    ["economy", "Economy · lowest cost"],
    ["local", "Local models only"],
  ].forEach(([value, label]) => {
    const option = el("option", "", label);
    option.value = value;
    mode.append(option);
  });
  tools.append(attach, mode);
  const send = el("button", "send-button");
  send.id = "send";
  send.type = "submit";
  send.setAttribute("aria-label", "Send message");
  send.append(icon("arrow-up"));
  bottom.append(tools, send);
  form.append(input, attachments, bottom);
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!input.value.trim() || state.busy) return;
    send.disabled = true;
    state.busy = true;
    try {
      await sendMessage(input.value.trim(), mode.value);
    } catch (error) {
      toast(error.message, true);
    } finally {
      state.busy = false;
      if (send.isConnected) send.disabled = false;
    }
  };
  wrap.append(
    form,
    el(
      "p",
      "composer-hint",
      preview
        ? "Interactive preview · Example responses, saved only in this browser."
        : "Your models. Your budget. You decide what happens next.",
    ),
  );
  return wrap;
}
function renderAttachments() {
  const root = $("#attachments");
  if (!root) return;
  root.replaceChildren();
  for (const a of state.attachments) {
    const n = el("div", "attachment-chip");
    n.append(icon("file"), el("span", "", a.name));
    const remove = button(
      "",
      () => {
        state.attachments = state.attachments.filter((x) => x.id !== a.id);
        renderAttachments();
      },
      "icon-button",
      "x",
    );
    remove.setAttribute("aria-label", "Remove " + a.name);
    n.append(remove);
    root.append(n);
  }
}
$("#upload").onchange = async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    if (state.attachments.length >= 5)
      throw Error("Attach up to five files at a time.");
    if (file.size > 5000000) throw Error("Choose a file under 5 MB.");
    if (!state.conv) {
      const c = await api("/api/conversations", {
        method: "POST",
        body: { title: "New conversation" },
      });
      state.conv = c.id;
    }
    const body = new FormData();
    body.append("file", file);
    const saved = await api("/api/conversations/" + state.conv + "/upload", {
      method: "POST",
      body,
    });
    state.attachments.push(saved);
    renderAttachments();
    toast("File attached");
  } catch (error) {
    toast(error.message, true);
  }
};
async function sendMessage(message, mode = "economy") {
  if (!state.conv) {
    const c = await api("/api/conversations", {
      method: "POST",
      body: { title: message.slice(0, 60) },
    });
    state.conv = c.id;
  }
  await api("/api/conversations/" + state.conv + "/chat", {
    method: "POST",
    body: { message, mode, attachments: state.attachments.map((a) => a.id) },
  });
  state.attachments = [];
  await refreshData();
  await navigate("chat", { id: state.conv });
}
function renderHome() {
  state.conv = null;
  state.attachments = [];
  const root = el("div", "home-view"),
    hero = el("section", "hero"),
    eyebrow = el("div", "eyebrow");
  eyebrow.append(
    icon("sparkles"),
    el("span", "", "A LITTLE LESS TO DO. A LITTLE MORE YOU."),
  );
  const title = el("h1");
  title.append(
    document.createTextNode("Big ideas. Everyday things."),
    el("br"),
    el("em", "", "Consider it a start."),
  );
  hero.append(
    eyebrow,
    title,
    el(
      "p",
      "",
      "A thought partner. A helping hand. A little space to make things happen.",
    ),
    composer({ home: true }),
  );
  const chips = el("div", "starter-chips");
  [
    [
      "Research something",
      "globe",
      "Help me research a topic. Ask what I want to learn and how detailed the answer should be.",
    ],
    ["Make something", "sparkles", ideas[1].prompt],
    ["Plan my day", "calendar", ideas[2].prompt],
    ["Find a good deal", "bag", ideas[0].prompt],
  ].forEach(([name, i, p]) =>
    chips.append(button(name, () => usePrompt(p), "chip", i)),
  );
  hero.append(chips);
  root.append(
    hero,
    section(
      "A little inspiration",
      button(
        "Explore your skills",
        () => navigate("skills"),
        "text-button",
        "arrow",
      ),
    ),
  );
  const grid = el("div", "inspiration-grid");
  for (const idea of ideas) {
    const card = button("", () => usePrompt(idea.prompt), "idea-card");
    card.append(art(idea.art));
    const copy = el("div", "idea-content");
    copy.append(
      el("div", "card-kicker", idea.category),
      el("h3", "", idea.title),
      el("p", "", idea.subtitle),
    );
    const foot = el("div", "idea-bottom");
    foot.append(el("span", "", idea.footer), icon("arrow"));
    copy.append(foot);
    card.append(copy);
    grid.append(card);
  }
  root.append(grid);
  const tasks = el("section", "home-tasks");
  tasks.append(
    section(
      "Keep things moving",
      button("View all tasks", () => navigate("tasks"), "text-button", "arrow"),
    ),
  );
  if (!state.tasks.length)
    tasks.append(
      empty(
        "Give your next goal a home.",
        "Save a task, then work through it with Static at your own pace.",
        button("Create your first task", () => taskForm(), "button", "plus"),
      ),
    );
  else state.tasks.slice(0, 3).forEach((t) => tasks.append(taskRow(t)));
  root.append(tasks);
  main.append(root);
}
function taskStatus(task) {
  if (task.status === "done") return ["Completed", "green"];
  if (task.run?.status === "awaiting_approval")
    return ["Needs approval", "orange"];
  if (["running", "queued"].includes(task.run?.status))
    return ["In progress", "purple"];
  if (task.run?.status === "failed") return ["Needs attention", "red"];
  return [
    task.steps.some((s) => s.status === "done")
      ? "In progress"
      : "Ready to start",
    "",
  ];
}
function taskSymbol(task) {
  const n = el("div", "task-symbol " + task.category);
  n.append(icon(categoryIcons[task.category] || "check-square"));
  return n;
}
function taskRow(task) {
  const b = button("", () => taskDetail(task), "task-row");
  const copy = el("div", "task-row-copy");
  copy.append(
    el("span", "task-row-title", task.title),
    el(
      "small",
      "",
      task.steps.length
        ? task.steps.filter((s) => s.status === "done").length +
            " of " +
            task.steps.length +
            " steps complete"
        : "A saved goal, ready when you are",
    ),
  );
  b.append(taskSymbol(task), copy, badge(...taskStatus(task)), icon("chevron"));
  return b;
}
function makeSearch(placeholder, onInput) {
  const wrap = el("label", "search-field");
  wrap.append(icon("search"));
  const input = el("input");
  input.type = "search";
  input.placeholder = placeholder;
  input.setAttribute("aria-label", placeholder);
  input.addEventListener("input", () => onInput(input.value));
  wrap.append(input);
  return wrap;
}
function tabs(options, current, onChange) {
  const n = el("div", "tabs");
  n.setAttribute("role", "group");
  n.setAttribute("aria-label", "Filter");
  options.forEach(([value, label]) => {
    const b = button(
      label,
      () => onChange(value),
      value === current ? "active" : "",
    );
    b.setAttribute("aria-pressed", String(value === current));
    n.append(b);
  });
  return n;
}
async function renderTasks() {
  const generation = state.generation;
  state.tasks = await api("/api/tasks");
  if (generation !== state.generation) return;
  updateShell();
  const root = el("div");
  root.append(
    heading(
      "A place for your plans.",
      "Small steps. Bigger possibilities.",
      button("New task", () => taskForm(), "button primary", "plus"),
    ),
  );
  const toolbar = el("div", "toolbar"),
    grid = el("div", "task-grid");
  const paint = () => {
    grid.replaceChildren();
    const tasks = state.tasks.filter(
      (t) =>
        (state.taskFilter === "all" ||
          (state.taskFilter === "done"
            ? t.status === "done"
            : t.status !== "done")) &&
        (t.title + " " + t.objective)
          .toLowerCase()
          .includes(state.taskQuery.toLowerCase()),
    );
    for (const task of tasks) {
      const card = el("article", "task-card"),
        top = el("div", "task-card-top");
      top.append(taskSymbol(task), badge(...taskStatus(task)));
      card.append(top, el("h3", "", task.title), el("p", "", task.objective));
      if (task.steps.length) {
        const track = el("div", "progress-track"),
          p = el("progress");
        p.max = task.steps.length;
        p.value = task.steps.filter((s) => s.status === "done").length;
        p.setAttribute("aria-label", "Task progress");
        track.append(p);
        card.append(track);
      }
      const foot = el("div", "task-card-bottom");
      foot.append(
        el("small", "", relativeDate(task.updated)),
        button("Open task", () => taskDetail(task), "text-button", "arrow"),
      );
      card.append(foot);
      grid.append(card);
    }
    if (!tasks.length)
      grid.append(
        empty(
          "Room for your next thing.",
          "Save a goal, outline the details, and start whenever you are ready.",
          button("New task", () => taskForm(), "button", "plus"),
        ),
      );
  };
  const tabContainer = el("div");
  const drawTabs = () => {
    tabContainer.replaceChildren(
      tabs(
        [
          ["all", "All tasks"],
          ["open", "In progress"],
          ["done", "Completed"],
        ],
        state.taskFilter,
        (v) => {
          state.taskFilter = v;
          drawTabs();
          paint();
        },
      ),
    );
  };
  drawTabs();
  const search = makeSearch("Find a task…", (q) => {
    state.taskQuery = q;
    paint();
  });
  $("input", search).value = state.taskQuery;
  toolbar.append(tabContainer, search);
  root.append(toolbar, grid);
  paint();
  main.append(root);
}
function taskForm(task) {
  const form = el("form"),
    title = field("Task name", task?.title || "", "text", {
      required: true,
      maxLength: 100,
      placeholder: "A weekend with room to wander",
    }),
    objective = field(
      "What would you like to accomplish?",
      task?.objective || "",
      "textarea",
      {
        required: true,
        maxLength: 12000,
        placeholder:
          "Add the goal, your budget, timing and anything Static should know.",
      },
    ),
    category = selectField(
      "Space",
      [
        ["life", "Life"],
        ["work", "Work"],
        ["research", "Research"],
        ["creative", "Creative"],
      ],
      task?.category || "life",
    );
  form.append(title.wrap, objective.wrap);
  if (!task) form.append(category.wrap);
  const actions = el("div", "form-actions"),
    save = el("button", "button primary", task ? "Save changes" : "Save task");
  save.type = "submit";
  actions.append(button("Cancel", closeModal, "button"), save);
  form.append(actions);
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!title.input.value.trim() || !objective.input.value.trim()) return;
    save.disabled = true;
    try {
      const body = {
        title: title.input.value.trim(),
        objective: objective.input.value.trim(),
      };
      if (!task) body.category = category.input.value;
      await api("/api/tasks" + (task ? "/" + task.id : ""), {
        method: task ? "PATCH" : "POST",
        body,
      });
      closeModal();
      await refreshData();
      await navigate("tasks");
      toast(task ? "Task updated" : "Task saved");
    } catch (error) {
      toast(error.message, true);
    } finally {
      save.disabled = false;
    }
  };
  showModal(task ? "Edit your task" : "What are we working toward?", form);
  title.input.focus();
}
function taskDetail(task) {
  const body = el("div"),
    meta = el("div", "task-detail-meta");
  meta.append(badge(task.category), badge(...taskStatus(task)));
  body.append(meta, el("p", "muted", task.objective));
  if (task.steps.length) {
    const list = el("ul", "plan-list");
    task.steps.forEach((step, index) => {
      const row = el("li", step.status === "done" ? "done" : ""),
        label = el("label", "toggle-label"),
        check = el("input");
      check.type = "checkbox";
      check.checked = step.status === "done";
      check.setAttribute("aria-label", step.title);
      check.onchange = async () => {
        check.disabled = true;
        try {
          const steps = task.steps.map((s, i) =>
            i === index
              ? { ...s, status: check.checked ? "done" : "pending" }
              : s,
          );
          const saved = await api("/api/tasks/" + task.id, {
            method: "PATCH",
            body: { steps },
          });
          Object.assign(task, saved);
          row.classList.toggle("done", check.checked);
        } catch (error) {
          check.checked = !check.checked;
          toast(error.message, true);
        } finally {
          check.disabled = false;
        }
      };
      label.append(check, document.createTextNode(step.title));
      row.append(label);
      list.append(row);
    });
    body.append(list);
  } else
    body.append(
      notice(
        "Start working with Static to build a step-by-step plan.",
        "neutral",
      ),
    );
  const actions = el("div", "form-actions");
  actions.append(button("Edit goal", () => taskForm(task), "button", "edit"));
  actions.append(
    button(
      task.status === "done" ? "Reopen" : "Mark complete",
      async () => {
        await api("/api/tasks/" + task.id, {
          method: "PATCH",
          body: { status: task.status === "done" ? "open" : "done" },
        });
        closeModal();
        await refreshData();
        await navigate("tasks");
      },
      "button",
      "check",
    ),
  );
  if (task.status !== "done")
    actions.append(
      button(
        activeStatuses.includes(task.run?.status)
          ? "View progress"
          : "Work on this",
        async (b) => {
          b.disabled = true;
          try {
            if (activeStatuses.includes(task.run?.status)) {
              closeModal();
              return navigate("chat", { id: task.conversation_id });
            }
            const run = await api("/api/tasks/" + task.id + "/start", {
              method: "POST",
              body: { mode: "economy" },
            });
            closeModal();
            state.attachments = [];
            await navigate("chat", { id: run.conversation_id });
          } finally {
            b.disabled = false;
          }
        },
        "button primary",
        "arrow",
      ),
    );
  else
    actions.append(
      button(
        "Open conversation",
        () => {
          closeModal();
          return navigate("chat", { id: task.conversation_id });
        },
        "button primary",
        "chat",
      ),
    );
  body.append(actions);
  showModal(task.title, body);
}
async function renderChat() {
  const conversationId = new URLSearchParams(location.search).get("id");
  if (conversationId !== state.conv) state.attachments = [];
  state.conv = conversationId;
  const generation = state.generation;
  const data = conversationId
    ? await api("/api/conversations/" + conversationId)
    : { messages: [], runs: [] };
  if (generation !== state.generation) return;
  const conv = state.conversations.find((c) => c.id === conversationId);
  const root = el("div", "chat-view"),
    top = el("div", "chat-top"),
    copy = el("div");
  const mark = el("div", "task-symbol");
  mark.append(icon("sparkles"));
  copy.append(
    el("h1", "", conv?.title || "Room for a new idea."),
    el(
      "p",
      "",
      preview
        ? "An example of working with Static"
        : "Talk it through. Make it happen.",
    ),
  );
  top.append(mark, copy);
  if (preview) top.append(badge("Demo", "purple"));
  root.append(top);
  const messages = el("div", "messages");
  messages.id = "messages";
  root.append(messages);
  paintMessages(data.messages);
  if (!data.messages.length) {
    const welcome = el("div", "welcome-mini"),
      img = el("img");
    img.src = "./assets/static.svg";
    img.alt = "";
    welcome.append(
      img,
      el("h3", "", "A little help goes a long way."),
      el(
        "p",
        "",
        "Research, write, plan, compare, create. What is on your mind?",
      ),
    );
    messages.append(welcome);
  }
  const runArea = el("div");
  runArea.id = "run-area";
  root.append(runArea, composer());
  main.append(root);
  paintMessages(data.messages);
  if (!data.messages.length)
    messages.append(
      empty(
        "What are we making possible?",
        "Ask Static to help you research, create, plan or organize.",
      ),
    );
  renderAttachments();
  const run = data.runs[0];
  if (run) {
    state.run = run.id;
    state.after = 0;
    await pollRun(run.id, generation);
  }
}
function paintMessages(messages) {
  const container = $("#messages");
  if (!container) return;
  container.replaceChildren();
  for (const msg of messages) {
    if (!["user", "assistant"].includes(msg.role)) continue;
    const row = el("article", "message " + msg.role);
    row.setAttribute(
      "aria-label",
      msg.role === "user" ? "Your message" : "Static response",
    );
    if (msg.role === "assistant") {
      const logo = el("img");
      logo.src = "./assets/static.svg";
      logo.alt = "";
      row.append(logo);
    }
    const copy = el("div", "message-content");
    copy.append(
      el("div", "message-label", "Static"),
      markdown(msg.content, downloadFile),
    );
    row.append(copy);
    container.append(row);
  }
}
function activityDescription(event) {
  const d = event.data;
  const name = skillInfo[d.name]?.[0] || d.name;
  switch (event.kind) {
    case "model":
      return "Using " + d.name + (d.role ? " · " + d.role : "");
    case "tool_start":
      return name + " started";
    case "tool_done":
      return name + " finished";
    case "tool_error":
      return name + ": " + d.error;
    case "error":
      return d.message;
    case "media":
      return d.kind + " generation submitted";
    case "artifact":
      return "Saved " + d.name;
    default:
      return null;
  }
}
async function pollRun(runId, generation) {
  if (generation !== state.generation || state.page !== "chat") return;
  try {
    const run = await api("/api/runs/" + runId + "?after=" + state.after);
    if (generation !== state.generation) return;
    const area = $("#run-area");
    if (!area) return;
    let strip = $("#run-strip");
    if (!strip) {
      strip = el("div", "run-strip");
      strip.id = "run-strip";
      area.append(strip);
    }
    strip.replaceChildren();
    const running = ["running", "queued"].includes(run.status);
    strip.append(
      running
        ? el("span", "spinner")
        : icon(run.status === "completed" ? "check" : "clock"),
      el(
        "span",
        "",
        {
          running: preview ? "Showing an example…" : "Working on it…",
          queued: "Ready to begin…",
          completed: preview ? "Example complete" : "Work completed",
          awaiting_approval: "A decision for you",
          cancelled: "Stopped",
          failed: "This run needs attention",
          interrupted: "Interrupted — send a follow-up to continue",
        }[run.status] || run.status,
      ),
      el("span", "muted", "· " + money(run.spent)),
    );
    if (activeStatuses.includes(run.status))
      strip.append(
        button(
          "Stop",
          async () => {
            await api("/api/runs/" + runId + "/stop", { method: "POST" });
            clearTimeout(state.poll);
            await pollRun(runId, generation);
          },
          "button compact",
          "stop",
        ),
      );
    $("#send").disabled = activeStatuses.includes(run.status);
    $("#prompt").disabled = activeStatuses.includes(run.status);
    for (const event of run.events) {
      state.after = Math.max(state.after, event.id);
      const description = activityDescription(event);
      if (description) {
        let details = $("#activity");
        if (!details) {
          details = el("details", "activity-panel");
          details.id = "activity";
          details.append(el("summary", "", "Activity · actions and tools"));
          const list = el("div", "activity-list");
          details.append(list);
          area.append(details);
        }
        const row = el("div", "activity-row");
        row.append(
          icon(event.kind.includes("error") ? "shield" : "bolt"),
          el("span", "", description),
        );
        $(".activity-list", details).append(row);
      }
      if (event.kind === "plan") {
        let plan = $("#run-plan");
        if (!plan) {
          plan = el("ul", "plan-list");
          plan.id = "run-plan";
          area.append(plan);
        }
        plan.replaceChildren();
        for (const step of event.data.steps) {
          const li = el("li", step.status === "done" ? "done" : "");
          li.append(
            icon(step.status === "done" ? "check" : "clock"),
            el("span", "", step.title),
          );
          plan.append(li);
        }
      }
    }
    let approvals = $("#approvals");
    if (!approvals) {
      approvals = el("div");
      approvals.id = "approvals";
      area.append(approvals);
    }
    approvals.replaceChildren();
    for (const approval of run.approvals) {
      const card = el("div", "approval-card");
      card.append(
        el(
          "h3",
          "",
          preview ? "Try an example approval" : "Approve this generation?",
        ),
      );
      const args = approval.args.arguments || approval.args;
      const profile = approval.args.profile || {};
      card.append(
        el("p", "", String(args.prompt || "Media generation")),
        el(
          "p",
          "muted",
          (profile.model || args.kind || "Media") +
            " · " +
            (preview
              ? "Simulated · no charge"
              : money(approval.cost) +
                " cost reservation. Provider billing may differ."),
        ),
      );
      const review = el("details");
      review.append(
        el("summary", "", "Generation details"),
        el("pre", "", JSON.stringify({ arguments: args, profile }, null, 2)),
      );
      card.append(review);
      const actions = el("div", "approval-actions");
      for (const [label, allow] of [
        [preview ? "Approve example" : "Approve generation", true],
        ["Decline", false],
      ])
        actions.append(
          button(
            label,
            async (b) => {
              b.disabled = true;
              try {
                await api("/api/approvals/" + approval.id, {
                  method: "POST",
                  body: { allow },
                });
                clearTimeout(state.poll);
                await pollRun(runId, generation);
              } finally {
                if (b.isConnected) b.disabled = false;
              }
            },
            "button" + (allow ? " primary" : ""),
          ),
        );
      card.append(actions);
      approvals.append(card);
    }
    if (run.error && !$("#run-error")) {
      const error = notice(run.error, "error");
      error.id = "run-error";
      area.append(error);
    }
    if (activeStatuses.includes(run.status))
      state.poll = setTimeout(
        () => pollRun(runId, generation),
        run.status === "awaiting_approval" ? 2500 : 900,
      );
    else {
      const data = await api("/api/conversations/" + state.conv);
      if (generation !== state.generation) return;
      paintMessages(data.messages);
      await refreshData();
    }
  } catch (error) {
    if (generation !== state.generation) return;
    toast(error.message, true);
    const area = $("#run-area");
    if (area && !$("#retry-poll")) {
      const retry = button(
        "Reconnect to this task",
        () => {
          retry.remove();
          return pollRun(runId, generation);
        },
        "button",
        "refresh",
      );
      retry.id = "retry-poll";
      area.append(retry);
    }
  }
}
async function downloadFile(id, name) {
  try {
    const blob = await api("/api/artifacts/" + id + "/download", {
      blob: true,
    });
    downloadBlob(blob, name);
  } catch (error) {
    toast(error.message, true);
  }
}
function renderCreate() {
  const root = el("div");
  root.append(
    heading(
      "A blank canvas. All yours.",
      "From a passing thought to something you can open, hold, or share.",
    ),
  );
  const types = el("div", "create-types");
  types.setAttribute("role", "group");
  types.setAttribute("aria-label", "Creation type");
  const content = el("div");
  const paint = () => {
    types.replaceChildren();
    const type =
      creationTypes.find((t) => t.id === state.createType) || creationTypes[0];
    for (const t of creationTypes) {
      const b = button(
        t.name,
        () => {
          state.createType = t.id;
          paint();
        },
        "create-type" + (t.id === type.id ? " selected" : ""),
        t.icon,
      );
      b.setAttribute("aria-pressed", String(t.id === type.id));
      types.append(b);
    }
    content.replaceChildren();
    const layout = el("div", "create-layout"),
      form = el("form", "panel");
    form.append(panelHeading(type.label));
    const prompt = field("Your idea", "", "textarea", {
      required: true,
      maxLength: 14000,
      placeholder: type.placeholder,
    });
    prompt.input.id = "create-prompt";
    form.append(prompt.wrap);
    let format;
    if (type.formats) {
      format = selectField("Format", type.formats, type.formats[0][0]);
      format.input.id = "create-format";
      form.append(format.wrap);
    }
    form.append(
      el(
        "p",
        "muted small",
        preview
          ? "Try it out with a downloadable example. This preview uses scripted responses."
          : type.note,
      ),
    );
    const actions = el("div", "form-actions"),
      submit = el("button", "button primary");
    submit.type = "submit";
    submit.append(
      icon("sparkles"),
      document.createTextNode(
        preview ? "Try an example" : "Create with Static",
      ),
    );
    actions.append(submit);
    form.append(actions);
    form.onsubmit = async (e) => {
      e.preventDefault();
      submit.disabled = true;
      state.conv = null;
      state.attachments = [];
      let request = prompt.input.value.trim();
      if (!request) {
        submit.disabled = false;
        return;
      }
      const formatValue = format?.input.value;
      const instructions =
        type.id === "document"
          ? `Create a ${formatValue} document file using file_create. `
          : type.id === "3d"
            ? formatValue === "procedural"
              ? "Create local OBJ geometry using mesh_create. "
              : "Create a generative 3D model using media_generate, kind 3d. "
            : ["image", "video"].includes(type.id)
              ? `Generate a ${type.id} using media_generate. `
              : "Help with this everyday task. Use email_draft or calendar_create for a downloadable draft or event file when appropriate. Ask for any missing date or timezone. ";
      try {
        await sendMessage(instructions + request);
      } catch (error) {
        toast(error.message, true);
      } finally {
        if (submit.isConnected) submit.disabled = false;
      }
    };
    const examples = el("div", "create-examples");
    examples.append(el("p", "muted small", "A FEW STARTING POINTS"));
    type.examples.forEach((text, i) => {
      const b = button(
        "",
        () => {
          prompt.input.value = text;
          prompt.input.focus();
        },
        "example-button",
      );
      const copy = el("div");
      copy.append(
        el("strong", "", text),
        el(
          "small",
          "",
          [
            "Make it your own",
            "Start small. See where it goes.",
            "A thought worth exploring",
          ][i],
        ),
      );
      b.append(icon(type.icon), copy, icon("arrow"));
      examples.append(b);
    });
    const n = el("div", "live-note");
    n.append(
      icon("shield"),
      el(
        "span",
        "",
        preview
          ? "No model calls or charges in the preview."
          : "Paid generation always asks for your approval.",
      ),
    );
    examples.append(n);
    layout.append(form, examples);
    content.append(layout);
  };
  paint();
  root.append(types, content);
  main.append(root);
}
function fileKind(file) {
  if (/\.(svg|png|jpe?g|webp|gif)$/i.test(file.name)) return "image";
  if (/\.(mp4|webm|mov)$/i.test(file.name)) return "video";
  if (/\.(obj|glb|gltf|stl)$/i.test(file.name)) return "cube";
  if (/\.csv$/i.test(file.name)) return "csv";
  return "doc";
}
async function previewFile(file) {
  const body = el("div");
  body.append(
    el(
      "p",
      "muted",
      file.name + " · " + Math.max(1, Math.round(file.size / 1024)) + " KB",
    ),
  );
  if (
    /\.(md|txt|csv|json|obj|py|ya?ml|js|css|ics|eml)$/i.test(file.name) &&
    file.size < 250000
  ) {
    const content = await api("/api/artifacts/" + file.id + "/download", {
      blob: true,
    });
    body.append(el("pre", "", await content.text()));
  } else
    body.append(
      notice("Download this file to open it in your preferred app.", "neutral"),
    );
  body.append(
    button(
      "Download file",
      () => downloadFile(file.id, file.name),
      "button primary",
      "download",
    ),
  );
  showModal(file.name, body);
}
async function renderLibrary() {
  const generation = state.generation;
  const [files, jobs] = await Promise.all([
    api("/api/artifacts"),
    api("/api/media"),
  ]);
  if (generation !== state.generation) return;
  const root = el("div");
  root.append(
    heading(
      "Good work deserves a home.",
      "Everything you make with Static, together in one place.",
      button(
        "Create something",
        () => navigate("create"),
        "button primary",
        "plus",
      ),
    ),
  );
  const toolbar = el("div", "toolbar"),
    tabContainer = el("div"),
    grid = el("div", "library-grid");
  let query = "";
  const paint = () => {
    grid.replaceChildren();
    const filtered = files.filter(
      (f) =>
        (state.fileFilter === "all" || fileKind(f) === state.fileFilter) &&
        f.name.toLowerCase().includes(query.toLowerCase()),
    );
    filtered.forEach((file) => {
      const kind = fileKind(file),
        card = el("article", "file-card"),
        artwork = el("div", "file-art " + kind);
      artwork.append(
        icon(
          {
            doc: "file",
            csv: "chart",
            cube: "cube",
            image: "image",
            video: "video",
          }[kind],
        ),
      );
      const info = el("div", "file-info");
      info.append(el("h3", "", file.name));
      const meta = el("div", "file-meta");
      meta.append(
        el(
          "span",
          "",
          file.name.split(".").pop().toUpperCase() +
            " · " +
            Math.max(1, Math.round(file.size / 1024)) +
            " KB",
        ),
        el("span", "", relativeDate(file.created)),
      );
      const actions = el("div", "file-buttons");
      actions.append(
        button("Open", () => previewFile(file), "text-button", "external"),
        button(
          "Download",
          () => downloadFile(file.id, file.name),
          "button compact",
          "download",
        ),
      );
      info.append(meta, actions);
      card.append(artwork, info);
      grid.append(card);
    });
    if (!filtered.length)
      grid.append(
        empty(
          "Something good will land here.",
          "Create a document, an image, a 3D model or a useful little file to get started.",
          button("Open Create", () => navigate("create"), "button", "sparkles"),
        ),
      );
  };
  const drawTabs = () =>
    tabContainer.replaceChildren(
      tabs(
        [
          ["all", "All files"],
          ["doc", "Documents"],
          ["image", "Images"],
          ["cube", "3D"],
          ["video", "Video"],
          ["csv", "Data"],
        ],
        state.fileFilter,
        (v) => {
          state.fileFilter = v;
          drawTabs();
          paint();
        },
      ),
    );
  drawTabs();
  toolbar.append(
    tabContainer,
    makeSearch("Find a file…", (q) => {
      query = q;
      paint();
    }),
  );
  root.append(toolbar, grid);
  paint();
  if (jobs.length) {
    const panel = el("section", "panel");
    panel.append(
      panelHeading(
        "Generations",
        "External generations continue while the Python server is running.",
      ),
    );
    panel.append(
      button(
        "Refresh status",
        async () => {
          await api("/api/media/refresh", { method: "POST" });
          await navigate("library", {}, false);
        },
        "button compact",
        "refresh",
      ),
    );
    for (const job of jobs) {
      const row = el("div", "job-row"),
        copy = el("div");
      copy.append(
        el("strong", "", job.kind + " generation"),
        el("small", "", job.error || relativeDate(job.created)),
      );
      row.append(copy, badge(job.status));
      if (
        ["starting", "processing", "submitting", "unknown"].includes(job.status)
      )
        row.append(
          button(
            "Cancel",
            async () => {
              await api("/api/media/" + job.id + "/cancel", { method: "POST" });
              await navigate("library", {}, false);
            },
            "button compact",
          ),
        );
      panel.append(row);
    }
    root.append(panel);
  }
  main.append(root);
}
async function renderSkills() {
  const generation = state.generation;
  const skills = await api("/api/skills");
  if (generation !== state.generation) return;
  const root = el("div");
  root.append(
    heading(
      "A few extra hands.",
      "Choose what Static can help you with. Switch skills on or off at any time.",
    ),
  );
  const toolbar = el("div", "toolbar"),
    tabContainer = el("div"),
    grid = el("div", "skill-grid");
  let query = "";
  const paint = () => {
    grid.replaceChildren();
    const filtered = skills.filter((s) => {
      const meta = skillInfo[s.name];
      const category = meta?.[3] || s.category;
      return (
        (state.skillFilter === "all" || category === state.skillFilter) &&
        ((meta?.[0] || s.name) + " " + s.description)
          .toLowerCase()
          .includes(query.toLowerCase())
      );
    });
    for (const skill of filtered) {
      const meta = skillInfo[skill.name] || [
          skill.name,
          "sparkles",
          skill.description,
          skill.category,
        ],
        card = el("article", "skill-card"),
        top = el("div", "skill-card-top"),
        symbol = el("div", "task-symbol");
      symbol.append(icon(meta[1]));
      const toggle = el("input", "switch");
      toggle.type = "checkbox";
      toggle.checked = !state.settings.disabled_skills.includes(skill.name);
      toggle.setAttribute("aria-label", "Enable " + meta[0]);
      toggle.onchange = async () => {
        toggle.disabled = true;
        const desired = toggle.checked;
        try {
          const settings = structuredClone(state.settings);
          settings.disabled_skills = settings.disabled_skills.filter(
            (s) => s !== skill.name,
          );
          if (!desired) settings.disabled_skills.push(skill.name);
          await saveSettings(settings, "Skill updated");
        } catch (error) {
          toggle.checked = !desired;
          toast(error.message, true);
        } finally {
          toggle.disabled = false;
        }
      };
      top.append(symbol, toggle);
      const bottom = el("div", "skill-card-bottom");
      bottom.append(
        el("span", "", meta[3]),
        badge(
          skill.approval ? "Approval required" : "Ready to use",
          skill.approval ? "orange" : "",
        ),
      );
      card.append(top, el("h3", "", meta[0]), el("p", "", meta[2]), bottom);
      grid.append(card);
    }
    if (!filtered.length)
      grid.append(empty("No skills found.", "Try another category or search."));
  };
  const drawTabs = () =>
    tabContainer.replaceChildren(
      tabs(
        [
          ["all", "All skills"],
          ["Research", "Research"],
          ["Create", "Create"],
          ["Organize", "Organize"],
          ["Files", "Files"],
          ["Agents", "Agents"],
        ],
        state.skillFilter,
        (v) => {
          state.skillFilter = v;
          drawTabs();
          paint();
        },
      ),
    );
  drawTabs();
  toolbar.append(
    tabContainer,
    makeSearch("Find a skill…", (q) => {
      query = q;
      paint();
    }),
  );
  root.append(toolbar, grid);
  paint();
  const n = el("div", "live-note");
  n.append(
    icon("plug"),
    el(
      "span",
      "",
      "Static skills are extensible Python tools. See the repository’s skill guide to add your own.",
    ),
  );
  root.append(n);
  main.append(root);
}
function checkbox(label, value, ariaLabel) {
  const wrap = el("label", "toggle-label"),
    input = el("input");
  input.type = "checkbox";
  input.checked = Boolean(value);
  if (ariaLabel) input.setAttribute("aria-label", ariaLabel);
  wrap.append(input, document.createTextNode(label));
  return { wrap, input };
}
function modelCard(model, index) {
  const details = el("details", "model-card");
  details.dataset.modelId = model.id;
  const summary = el("summary"),
    symbol = el("div", "task-symbol");
  symbol.append(icon(model.local ? "leaf" : "bolt"));
  const copy = el("div");
  copy.append(el("strong", "", model.name), el("small", "", model.model));
  summary.append(
    symbol,
    copy,
    badge(model.local ? "Local" : "Cloud", model.local ? "green" : "purple"),
    icon("down"),
  );
  details.append(summary);
  const content = el("div", "model-form"),
    grid = el("div", "form-grid");
  const name = field("Connection name", model.name, "text", {
      required: true,
      maxLength: 120,
    }),
    modelName = field("Model ID", model.model, "text", {
      required: true,
      maxLength: 200,
    }),
    base = field("API base URL", model.base_url, "url", { required: true }),
    key = field("API key environment variable", model.key_env, "text", {
      placeholder: "STATIC_API_KEY",
      pattern: "[A-Z0-9_]*",
    });
  grid.append(name.wrap, modelName.wrap, base.wrap, key.wrap);
  content.append(grid);
  const local = checkbox("Local model · no per-token API cost", model.local);
  content.append(local.wrap);
  const priceGrid = el("div", "form-grid");
  const inputPrice = field(
      "Input price / 1M tokens (USD)",
      model.input_per_million,
      "number",
      { min: 0, max: 10000, step: "any", required: true },
    ),
    outputPrice = field(
      "Output price / 1M tokens (USD)",
      model.output_per_million,
      "number",
      { min: 0, max: 10000, step: "any", required: true },
    );
  priceGrid.append(inputPrice.wrap, outputPrice.wrap);
  content.append(priceGrid);
  const pricing = checkbox(
    "I verified this provider’s current prices",
    model.pricing_confirmed,
  );
  content.append(pricing.wrap);
  const syncLocal = () => {
    inputPrice.input.disabled = local.input.checked;
    outputPrice.input.disabled = local.input.checked;
    pricing.wrap.hidden = local.input.checked;
  };
  local.input.onchange = syncLocal;
  syncLocal();
  const advanced = el("details");
  advanced.append(el("summary", "", "Advanced routing"));
  const advancedGrid = el("div", "form-grid"),
    max = field("Maximum output tokens", model.max_output_tokens, "number", {
      min: 256,
      max: 8192,
      step: 1,
      required: true,
    }),
    tokenParam = selectField(
      "Token limit parameter",
      [
        ["max_tokens", "max_tokens"],
        ["max_completion_tokens", "max_completion_tokens"],
      ],
      model.token_parameter,
    );
  advancedGrid.append(max.wrap, tokenParam.wrap);
  const tools = checkbox("Supports tool calling", model.tool_calling);
  advanced.append(advancedGrid, tools.wrap);
  const roles = el("div", "role-grid");
  const roleFields = [
    "coordinator",
    "researcher",
    "writer",
    "coder",
    "planner",
  ].map((role) => {
    const f = checkbox(
      role,
      model.roles.includes(role),
      name.input.value + " " + role,
    );
    roles.append(f.wrap);
    return [role, f.input];
  });
  advanced.append(roles);
  content.append(advanced);
  const actions = el("div", "model-actions"),
    result = el(
      "span",
      "",
      preview
        ? "Example configuration"
        : state.keys[model.id]
          ? "Key available or local model"
          : "Key not found on server",
    );
  actions.append(
    button(
      "Test connection",
      async (b) => {
        b.disabled = true;
        result.textContent = "Checking…";
        try {
          const response = await api("/api/models/" + model.id + "/test", {
            method: "POST",
          });
          result.textContent = preview
            ? "Simulated connection"
            : response.message ||
              (response.ok ? "Connected" : "Connection unavailable");
          if (response.note) toast(response.note);
        } catch (error) {
          result.textContent = "Connection failed";
          toast(error.message, true);
        } finally {
          b.disabled = false;
        }
      },
      "button compact",
      "plug",
    ),
    result,
  );
  actions.append(
    button(
      "Remove",
      async () => {
        if (state.settings.models.length <= 1)
          throw Error("Keep at least one model connection.");
        const settings = structuredClone(state.settings);
        settings.models.splice(index, 1);
        await saveSettings(settings, "Connection removed");
        await navigate("connections", {}, false);
      },
      "button compact danger",
      "trash",
    ),
  );
  content.append(
    actions,
    el(
      "p",
      "muted small",
      "Save connection changes before testing. Keys belong in the server environment, never in this form.",
    ),
  );
  details.append(content);
  return {
    element: details,
    value: () => ({
      ...model,
      name: name.input.value.trim(),
      model: modelName.input.value.trim(),
      base_url: base.input.value.trim().replace(/\/$/, ""),
      key_env: key.input.value.trim(),
      local: local.input.checked,
      input_per_million: local.input.checked
        ? 0
        : Number(inputPrice.input.value),
      output_per_million: local.input.checked
        ? 0
        : Number(outputPrice.input.value),
      pricing_confirmed: pricing.input.checked,
      tool_calling: tools.input.checked,
      roles: roleFields.filter(([, i]) => i.checked).map(([role]) => role),
      max_output_tokens: Number(max.input.value),
      token_parameter: tokenParam.input.value,
    }),
  };
}
function addModel() {
  const form = el("form");
  form.append(
    el(
      "p",
      "muted",
      "Connect an OpenAI-compatible model endpoint. Your API key stays in an environment variable on the Python server.",
    ),
  );
  const kind = selectField(
      "Connection type",
      [
        ["local", "Local · Ollama"],
        ["cloud", "Cloud · compatible API"],
      ],
      "local",
    ),
    name = field("Connection name", "", "text", {
      required: true,
      placeholder: "My model",
      maxLength: 120,
    }),
    model = field("Model ID", "qwen3:4b", "text", {
      required: true,
      maxLength: 200,
    }),
    url = field("API base URL", "http://localhost:11434/v1", "url", {
      required: true,
    }),
    key = field("Key environment variable", "", "text", {
      pattern: "[A-Z0-9_]*",
      placeholder: "STATIC_API_KEY",
    }),
    inputPrice = field("Input price / 1M tokens (USD)", 0, "number", {
      min: 0,
      max: 10000,
      step: "any",
      required: true,
    }),
    outputPrice = field("Output price / 1M tokens (USD)", 0, "number", {
      min: 0,
      max: 10000,
      step: "any",
      required: true,
    }),
    verified = checkbox("I verified the provider’s current prices", false);
  const cloudFields = el("div");
  cloudFields.append(
    key.wrap,
    inputPrice.wrap,
    outputPrice.wrap,
    verified.wrap,
  );
  cloudFields.hidden = true;
  kind.input.onchange = () => {
    const cloud = kind.input.value === "cloud";
    cloudFields.hidden = !cloud;
    verified.input.required = cloud;
    url.input.value = cloud ? "" : "http://localhost:11434/v1";
    url.input.placeholder = cloud ? "https://your-provider.example/v1" : "";
    model.input.value = cloud ? "" : "qwen3:4b";
  };
  form.append(kind.wrap, name.wrap, model.wrap, url.wrap, cloudFields);
  const save = el("button", "button primary", "Add connection");
  save.type = "submit";
  form.append(save);
  form.onsubmit = async (e) => {
    e.preventDefault();
    save.disabled = true;
    try {
      const local = kind.input.value === "local";
      const settings = structuredClone(state.settings);
      settings.models.push({
        id: "model-" + crypto.randomUUID().slice(0, 8),
        name: name.input.value.trim(),
        model: model.input.value.trim(),
        base_url: url.input.value.trim().replace(/\/$/, ""),
        key_env: local ? "" : key.input.value.trim(),
        local,
        input_per_million: local ? 0 : Number(inputPrice.input.value),
        output_per_million: local ? 0 : Number(outputPrice.input.value),
        pricing_confirmed: local ? false : verified.input.checked,
        tool_calling: true,
        roles: ["coordinator", "researcher", "writer", "coder", "planner"],
        max_output_tokens: 2048,
        token_parameter: "max_tokens",
      });
      await saveSettings(settings, "Connection added");
      closeModal();
      await navigate("connections", {}, false);
    } catch (error) {
      toast(error.message, true);
    } finally {
      save.disabled = false;
    }
  };
  showModal("Bring your own model.", form);
}
async function renderConnections() {
  const root = el("div");
  root.append(
    heading(
      "Your models. More possibilities.",
      "Start locally, or connect the tools that work for you.",
      button("Add model", addModel, "button primary", "plus"),
    ),
  );
  if (preview)
    root.append(
      notice(
        "Connections in this preview are examples. No endpoints are contacted and no API keys are collected. Run the Python app to connect real models.",
      ),
    );
  const metrics = el("div", "connection-summary");
  for (const [label, value, detail] of [
    [
      "Model connections",
      String(state.settings.models.length),
      "Available to the coordinator",
    ],
    ["Routing", "Economy", "Lowest configured model cost"],
    [
      "Today",
      money(state.spent),
      money(state.settings.daily_budget_usd) + " daily limit",
    ],
  ]) {
    const m = el("div", "metric");
    m.append(
      el("small", "", label),
      el("strong", "", value),
      el("span", "", detail),
    );
    metrics.append(m);
  }
  root.append(metrics);
  const form = el("form");
  form.append(section("Language models"));
  const cards = state.settings.models.map(modelCard);
  cards.forEach((c) => form.append(c.element));
  const mediaPanel = el("section", "panel");
  mediaPanel.append(
    panelHeading(
      "A studio, connected.",
      "Choose Replicate models for image, video and generative 3D. A conservative cost reservation is required for each profile.",
    ),
  );
  const mediaGrid = el("div", "media-grid");
  const mediaFields = [];
  for (const kind of ["image", "video", "3d"]) {
    const profile = state.settings.media[kind] || {
        model: "",
        prompt_field: "prompt",
        reserve_usd: 0,
        inputs: {},
      },
      card = el("div", "media-profile"),
      h = el("h3");
    h.append(
      icon(kind === "3d" ? "cube" : kind),
      document.createTextNode(
        { image: "Images", video: "Video", "3d": "3D models" }[kind],
      ),
    );
    card.append(h);
    const model = field("Replicate model", profile.model, "text", {
        placeholder: "owner/model or owner/model:version",
      }),
      prompt = field("Prompt field", profile.prompt_field, "text", {
        required: true,
        pattern: "[a-zA-Z0-9_]{1,80}",
      }),
      reserve = field("Cost reservation (USD)", profile.reserve_usd, "number", {
        min: 0,
        max: 100,
        step: "any",
        required: true,
      }),
      inputs = field(
        "Default inputs (JSON)",
        JSON.stringify(profile.inputs, null, 2),
        "textarea",
        { maxLength: 16000 },
      );
    card.append(model.wrap, prompt.wrap, reserve.wrap, inputs.wrap);
    mediaGrid.append(card);
    mediaFields.push([
      kind,
      () => {
        const parsed = JSON.parse(inputs.input.value || "{}");
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object")
          throw Error("Media defaults must be a JSON object.");
        return {
          model: model.input.value.trim(),
          prompt_field: prompt.input.value.trim(),
          reserve_usd: Number(reserve.input.value),
          inputs: parsed,
        };
      },
    ]);
  }
  mediaPanel.append(
    mediaGrid,
    el(
      "p",
      "muted small",
      state.keys.replicate
        ? "REPLICATE_API_TOKEN is available on the server."
        : "Set REPLICATE_API_TOKEN in the server environment to enable paid media.",
    ),
  );
  const links = el("div", "connection-links");
  for (const [label, url] of [
    ["Ollama models", "https://ollama.com/search"],
    ["Replicate models", "https://replicate.com/explore"],
    [
      "Connection guide",
      "https://github.com/MilkdromedaStudios/Static#connect-your-models",
    ],
  ]) {
    const link = el("a", "", label + " ↗");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    links.append(link);
  }
  mediaPanel.append(links);
  form.append(mediaPanel);
  const actions = el("div", "form-actions"),
    save = el("button", "button primary", "Save connections");
  save.type = "submit";
  actions.append(
    el(
      "span",
      "muted",
      "Prices are supplied by you. Static does not fetch provider pricing.",
    ),
    save,
  );
  form.append(actions);
  form.onsubmit = async (e) => {
    e.preventDefault();
    save.disabled = true;
    try {
      const settings = structuredClone(state.settings);
      settings.models = cards.map((c) => c.value());
      settings.media = Object.fromEntries(
        mediaFields.map(([kind, value]) => [kind, value()]),
      );
      await saveSettings(settings, "Connections saved");
      await navigate("connections", {}, false);
    } catch (error) {
      toast(error.message, true);
    } finally {
      if (save.isConnected) save.disabled = false;
    }
  };
  root.append(form);
  main.append(root);
}
function renderSettings() {
  const root = el("div", "settings-column");
  root.append(
    heading(
      "Make yourself at home.",
      "A workspace that feels a little more like you.",
    ),
  );
  const appearance = el("section", "panel");
  appearance.append(
    panelHeading(
      "A different kind of light.",
      "Choose your view. Your preference stays with this browser.",
    ),
  );
  const themes = el("div", "segmented");
  for (const [value, label, i] of [
    ["light", "Light", "sun"],
    ["dark", "Dark", "moon"],
    ["system", "System", "settings"],
  ]) {
    const b = button(
      label,
      () => {
        window.staticTheme.set(value);
        renderSettings();
      },
      "theme-choice" + (window.staticTheme.get() === value ? " selected" : ""),
      i,
    );
    b.setAttribute("aria-pressed", String(window.staticTheme.get() === value));
    themes.append(b);
  }
  appearance.append(themes);
  root.append(appearance);
  const form = el("form"),
    profile = el("section", "panel");
  profile.append(
    panelHeading(
      "A few things about you.",
      "Preferences you add here are shared with the models you use. Keep credentials out of this space.",
    ),
  );
  const displayName = field(
      "What should we call you?",
      state.settings.display_name,
      "text",
      { maxLength: 80, placeholder: "Your name" },
    ),
    preferences = field(
      "What would you like Static to keep in mind?",
      state.settings.preferences,
      "textarea",
      {
        maxLength: 3000,
        placeholder:
          "Keep answers concise. I prefer metric units. Ask before suggesting paid tools.",
      },
    );
  profile.append(displayName.wrap, preferences.wrap);
  const budget = el("section", "panel");
  budget.append(
    panelHeading(
      "Good help. A sensible budget.",
      "Estimates use your configured provider prices. Local models have no per-token API fee.",
    ),
  );
  const grid = el("div", "form-grid"),
    daily = field(
      "Daily limit (USD)",
      state.settings.daily_budget_usd,
      "number",
      { min: 0, max: 1000, step: "any", required: true },
    ),
    run = field(
      "Default limit per run (USD)",
      state.settings.run_budget_usd,
      "number",
      { min: 0, max: 100, step: "any", required: true },
    ),
    steps = field("Maximum steps per run", state.settings.max_steps, "number", {
      min: 1,
      max: 30,
      step: 1,
      required: true,
    }),
    search = selectField(
      "Web search",
      [
        ["duckduckgo", "DuckDuckGo · best effort"],
        ["brave", "Brave · API key required"],
      ],
      state.settings.search_provider,
    ),
    searchCost = field(
      "Brave search reservation (USD)",
      state.settings.search_reserve_usd,
      "number",
      { min: 0, max: 1, step: "any", required: true },
    );
  grid.append(daily.wrap, run.wrap, steps.wrap, search.wrap, searchCost.wrap);
  budget.append(
    grid,
    el(
      "p",
      "muted small",
      "Cloud calls stop when reservations reach a limit. Provider billing may differ from these estimates. Daily limits use UTC.",
    ),
  );
  const save = el("button", "button primary", "Save preferences");
  save.type = "submit";
  const actions = el("div", "form-actions");
  actions.append(save);
  form.append(profile, budget, actions);
  form.onsubmit = async (e) => {
    e.preventDefault();
    save.disabled = true;
    try {
      const settings = {
        ...structuredClone(state.settings),
        display_name: displayName.input.value.trim(),
        preferences: preferences.input.value.trim(),
        daily_budget_usd: Number(daily.input.value),
        run_budget_usd: Number(run.input.value),
        max_steps: Number(steps.input.value),
        search_provider: search.input.value,
        search_reserve_usd: Number(searchCost.input.value),
      };
      await saveSettings(settings, "Preferences saved");
    } catch (error) {
      toast(error.message, true);
    } finally {
      save.disabled = false;
    }
  };
  root.append(form);
  if (preview) {
    const panel = el("section", "panel");
    panel.append(
      panelHeading(
        "A fresh start for the preview.",
        "Reset the fictional tasks, sample conversations and preview settings saved in this browser. Download anything you want to keep first.",
      ),
    );
    panel.append(
      button(
        "Reset preview",
        () => {
          const body = el("div");
          body.append(
            el(
              "p",
              "muted",
              "This removes your edits and uploads from this browser’s preview and restores the example workspace. Your theme preference stays the same.",
            ),
          );
          const actions = el("div", "form-actions");
          actions.append(
            button("Keep my changes", closeModal, "button"),
            button(
              "Reset examples",
              async () => {
                const { resetDemo } = await import("./demo.js");
                resetDemo();
                closeModal();
                await refreshData();
                await navigate("home");
                toast("Preview reset");
              },
              "button primary",
            ),
          );
          body.append(actions);
          showModal("Reset the example workspace?", body);
        },
        "button",
        "refresh",
      ),
    );
    root.append(panel);
  }
  const about = el("div", "live-note");
  about.append(
    icon("shield"),
    el("span", "", "Static 0.2 · Open source · Your models, your workspace"),
  );
  root.append(about);
  main.replaceChildren(root);
}
function openSearch() {
  const body = el("div"),
    results = el("div", "modal-search-results");
  const render = (q) => {
    results.replaceChildren();
    const matches = [
      ...state.tasks.map((t) => ({
        id: t.id,
        title: t.title,
        type: "Task",
        action: () => taskDetail(t),
      })),
      ...state.conversations.map((c) => ({
        id: c.id,
        title: c.title,
        type: "Conversation",
        action: () => {
          closeModal();
          return navigate("chat", { id: c.id });
        },
      })),
    ]
      .filter((x) => x.title.toLowerCase().includes(q.toLowerCase()))
      .slice(0, 15);
    for (const m of matches) {
      const b = button("", m.action, "search-result");
      b.append(
        icon(m.type === "Task" ? "check-square" : "chat"),
        el("span", "", m.title),
        el("small", "", m.type),
      );
      results.append(b);
    }
    if (!matches.length)
      results.append(
        el(
          "p",
          "muted small",
          "Nothing found. Try a different search, or start a new conversation.",
        ),
      );
  };
  const search = makeSearch("Search your workspace…", render);
  body.append(search, results);
  render("");
  showModal("Find a little clarity.", body);
  $("input", search).focus();
}
$("#search-open").onclick = openSearch;
$("#search-top").onclick = openSearch;
async function init() {
  hydrateIcons();
  themeButton();
  $("#preview-badge").hidden = !preview;
  $("#runtime-label").textContent = preview
    ? "Interactive preview · Browser-only examples"
    : "Static · Your personal AI workspace";
  try {
    await refreshData();
    await route();
  } catch (error) {
    fatal(error);
  }
}
init();
