// Deliberately deterministic, browser-only examples. Never called by the Python app.
import { skillInfo } from "./catalog.js";
const KEY = "static-preview-v2";
const id = () => crypto.randomUUID().replaceAll("-", "");
const now = () => new Date().toISOString();
const ago = (days) => new Date(Date.now() - days * 86400000).toISOString();
const clone = (value) => JSON.parse(JSON.stringify(value));
const cube =
  "# Static preview — real example OBJ geometry\no Cube\nv -1 -1 -1\nv 1 -1 -1\nv 1 1 -1\nv -1 1 -1\nv -1 -1 1\nv 1 -1 1\nv 1 1 1\nv -1 1 1\nf 1 4 3 2\nf 5 6 7 8\nf 1 2 6 5\nf 2 3 7 6\nf 3 4 8 7\nf 4 1 5 8\n";
const illustration =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800"><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#ebe5fb"/><stop offset="1" stop-color="#c4b6ea"/></linearGradient><linearGradient id="s" x2="1" y2="1"><stop stop-color="#e7ddff"/><stop offset="1" stop-color="#8162bf"/></linearGradient></defs><rect width="1200" height="800" fill="url(#bg)"/><ellipse cx="630" cy="600" rx="270" ry="55" fill="#715099" opacity=".18"/><g transform="translate(600 355) rotate(-28)"><rect x="-195" y="-185" width="400" height="400" rx="120" fill="#8767b8"/><rect x="-220" y="-220" width="400" height="400" rx="120" fill="url(#s)"/><rect x="-125" y="-125" width="210" height="210" rx="46" fill="#c7b8e6"/></g><text x="55" y="740" font-family="sans-serif" font-size="18" fill="#624782">STATIC — ORIGINAL VECTOR EXAMPLE · NOT AN AI GENERATION</text></svg>';
function seed() {
  const conversations = [
    { id: "c1", title: "A more thoughtful workspace", created: ago(0) },
    { id: "c2", title: "A weekend with room to wander", created: ago(1) },
    { id: "c3", title: "Bring the launch to life", created: ago(2) },
  ];
  const settings = {
    display_name: "",
    preferences: "",
    models: [
      {
        id: "local",
        name: "Ollama · Qwen 3",
        model: "qwen3:4b",
        base_url: "http://localhost:11434/v1",
        key_env: "",
        input_per_million: 0,
        output_per_million: 0,
        local: true,
        pricing_confirmed: false,
        tool_calling: true,
        roles: ["coordinator", "researcher", "writer", "coder", "planner"],
        max_output_tokens: 2048,
        token_parameter: "max_tokens",
      },
    ],
    daily_budget_usd: 2,
    run_budget_usd: 0.25,
    max_steps: 12,
    search_provider: "duckduckgo",
    search_reserve_usd: 0.01,
    media: Object.fromEntries(
      ["image", "video", "3d"].map((k) => [
        k,
        { model: "", prompt_field: "prompt", inputs: {}, reserve_usd: 0 },
      ]),
    ),
    disabled_skills: [],
  };
  const tasks = [
    {
      id: "t1",
      title: "Refresh my workspace",
      objective:
        "Find a desk lamp and a few thoughtful details for a calmer workspace. Keep the total budget under $150. This is a fictional example; research has not been performed.",
      category: "research",
      status: "open",
      conversation_id: "c1",
      created: ago(0),
      updated: ago(0),
      steps: [
        { title: "Set the style and budget", status: "done" },
        { title: "Research a shortlist", status: "pending" },
        { title: "Compare total costs", status: "pending" },
      ],
    },
    {
      id: "t2",
      title: "Plan a slower weekend",
      objective:
        "Sketch a relaxed two-day trip with a walk, a good meal and room to explore. Ask me for my destination and budget before researching. This is a fictional example.",
      category: "life",
      status: "open",
      conversation_id: "c2",
      created: ago(1),
      updated: ago(1),
      steps: [
        { title: "Choose a destination", status: "pending" },
        { title: "Build a relaxed itinerary", status: "pending" },
        { title: "Prepare a packing list", status: "pending" },
      ],
    },
    {
      id: "t3",
      title: "Shape the next launch",
      objective:
        "Create a short launch checklist and a visual direction for a small personal project. Sample deliverables are already in the preview Library.",
      category: "creative",
      status: "done",
      conversation_id: "c3",
      created: ago(2),
      updated: ago(2),
      steps: [
        { title: "Define the idea", status: "done" },
        { title: "Draft the checklist", status: "done" },
        { title: "Create a visual direction", status: "done" },
      ],
    },
  ];
  const artifact = (name, mime, content, conversation_id) => ({
    id: id(),
    name,
    mime,
    content,
    conversation_id,
    run_id: "",
    size: new Blob([content]).size,
    created: ago(1),
  });
  return {
    settings,
    tasks,
    conversations,
    messages: {
      c1: [
        { role: "user", content: "Help me make my workspace a little calmer." },
        {
          role: "assistant",
          content:
            "**A little room to think.**\nThis is an example conversation. In the connected app, I would ask about your space and budget, research options and compare total costs.\nYour sample task is saved in Tasks. You can edit its goal and checklist.",
        },
      ],
      c2: [
        {
          role: "assistant",
          content:
            "**A weekend without a packed schedule.**\nThis sample task is ready for a destination and a budget. The connected app can research a plan and create calendar files for you to import.",
        },
      ],
      c3: [
        {
          role: "assistant",
          content:
            "**A starting point for your next idea.**\nThe preview Library contains an original SVG illustration, a Markdown checklist and a sample CSV. These are downloadable examples, not live AI generations.",
        },
      ],
    },
    runs: {},
    approvals: [],
    artifacts: [
      artifact(
        "launch-checklist.md",
        "text/markdown",
        "# Launch checklist\n\nStatic interactive preview — example file.\n\n- Define the audience and the problem\n- Make a small first version\n- Ask three people to try it\n- Refine the rough edges\n- Share the result\n",
        "c3",
      ),
      artifact("quiet-forms.svg", "image/svg+xml", illustration, "c3"),
      artifact(
        "example-budget.csv",
        "text/csv",
        "Item,Estimated cost\nDesk lamp,45\nNotebook,12\nPlant,18\n\n",
        "c1",
      ),
    ],
    media: [],
  };
}
let state;
try {
  const saved = localStorage.getItem(KEY);
  state = saved ? JSON.parse(saved) : seed();
  if (!state.settings || !Array.isArray(state.tasks))
    throw Error("Invalid preview data");
} catch {
  state = seed();
}
function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    throw Error(
      "Preview storage is full or disabled. Download files you want to keep, then reset the preview in Settings.",
    );
  }
}
function find(list, value, label) {
  const item = list.find((x) => x.id === value);
  if (!item) throw Error(label + " not found");
  return item;
}
function makeArtifact(run, name, mime, content) {
  const a = {
    id: id(),
    conversation_id: run.conversation_id,
    run_id: run.id,
    name,
    mime,
    content,
    size: new Blob([content]).size,
    created: now(),
  };
  state.artifacts.unshift(a);
  return a;
}
function finish(run, approved = false) {
  if (run.status === "completed" || run.status === "cancelled") return;
  const input = run.prompt.toLowerCase();
  let response =
    "**Preview result**\nThis is a scripted example. No model, website or external account was contacted.\n";
  let file;
  if (/(image|video|generative 3d)/.test(input) && !approved) {
    run.status = "awaiting_approval";
    const a = {
      id: id(),
      run_id: run.id,
      tool: "media_generate",
      cost: 0,
      status: "pending",
      args: {
        arguments: {
          kind: input.includes("video") ? "video" : "image",
          prompt: run.prompt,
        },
        profile: { model: "preview/example", reserve_usd: 0 },
      },
    };
    state.approvals.push(a);
    run.events.push({
      id: 3,
      kind: "status",
      data: { status: "awaiting_approval" },
    });
    return;
  }
  if (/video/.test(input)) {
    file = makeArtifact(
      run,
      "example-storyboard.md",
      "text/markdown",
      "# Video storyboard — preview example\n\nNo video has been generated. The connected app submits your prompt to your configured video model after approval.\n\n1. Wide shot: a calm, sunlit studio\n2. Slow camera move toward the subject\n3. A close detail, then a quiet fade\n",
    );
    response +=
      "I prepared a sample storyboard. Connect a video model in the Python app to generate actual footage.\n";
  } else if (/image|wallpaper|illustration/.test(input)) {
    file = makeArtifact(run, "quiet-forms.svg", "image/svg+xml", illustration);
    response +=
      "Here is a downloadable vector example. The connected app can generate an image using your configured model.\n";
  } else if (/3d|sphere|cylinder|obj|cube/.test(input)) {
    file = makeArtifact(run, "example-cube.obj", "text/plain", cube);
    response +=
      "This preview includes a real example cube mesh. The connected app can create the requested geometry or use your 3D provider.\n";
  } else if (/email|follow-up/.test(input)) {
    file = makeArtifact(
      run,
      "example-follow-up.eml",
      "message/rfc822",
      "Subject: A quick follow-up\r\nX-Unsent: 1\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nHi,\r\n\r\nThanks for your time. I wanted to follow up on our conversation and see what the next step might be.\r\n\r\nBest,\r\n",
    );
    response += "A sample email draft is ready to review. No email was sent.\n";
  } else if (/calendar|\.ics/.test(input)) {
    file = makeArtifact(
      run,
      "example-focus-time.ics",
      "text/calendar",
      "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Static//Preview//EN\r\nBEGIN:VEVENT\r\nUID:" +
        id() +
        "@static.local\r\nDTSTAMP:20260927T090000Z\r\nDTSTART:20261001T090000Z\r\nDTEND:20261001T100000Z\r\nSUMMARY:Example focus time — Static preview\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n",
    );
    response +=
      "Here is an example calendar file for October 1, 2026 at 09:00 UTC. Review the example date before importing it. Nothing was added to an account.\n";
  } else if (
    /csv|spreadsheet|budget/.test(input) &&
    !/compare|buy|shopping/.test(input)
  ) {
    file = makeArtifact(
      run,
      "example-budget.csv",
      "text/csv",
      "Category,Planned amount\nMaterials,50\nTools,25\nBuffer,15\n",
    );
    response +=
      "Here is a small sample budget spreadsheet. In the connected app, I can use your figures and analyze an uploaded CSV.\n";
  } else if (/document|file|proposal|brief|markdown|checklist/.test(input)) {
    file = makeArtifact(
      run,
      "example-project-plan.md",
      "text/markdown",
      "# Project plan\n\nStatic interactive preview — example document.\n\n## Goal\nTurn a clear idea into a small, useful result.\n\n## Steps\n1. Define the audience and requirements\n2. Research the options\n3. Make a first version\n4. Review and improve\n\n## Budget\nStart locally. Approve any external generation separately.\n",
    );
    response +=
      "Your example Markdown file is ready. The connected app can write a tailored PDF, Word document or other requested format.\n";
  } else if (/compare|shopping|buy|desk|deal/.test(input))
    response +=
      "In the connected app, I can research current seller pages, compare item price plus shipping and known tax, then give you a shortlist.\nWhat are you looking for, which country are you shopping in, and what is your total budget?\nNo products have been searched or purchased in this preview.";
  else
    response +=
      "Here is how we could approach it:\n1. Define the outcome and any constraints.\n2. Gather the information we need.\n3. Create the deliverable and review it together.\nTry Create for downloadable examples, or save a goal in Tasks. The connected Python app uses your models to tailor its response.";
  if (file)
    response += `\n[Download ${file.name}](/api/artifacts/${file.id}/download)`;
  const conv = (state.messages[run.conversation_id] ||= []);
  conv.push({ id: id(), role: "assistant", content: response, created: now() });
  run.status = "completed";
  run.events.push({ id: 4, kind: "status", data: { status: "completed" } });
}
export async function demoRequest(path, method = "GET", body) {
  const url = new URL("https://preview.invalid" + path);
  const parts = url.pathname.split("/").filter(Boolean);
  const group = parts[1],
    value = parts[2],
    action = parts[3];
  const data = typeof body === "string" ? JSON.parse(body) : body;
  let result;
  if (group === "health") return { ok: true, version: "0.2.0", preview: true };
  if (group === "settings") {
    if (method === "PUT") {
      state.settings = clone(data);
      save();
    }
    return clone({
      settings: state.settings,
      keys: { brave: false, replicate: false, local: true },
      spent_today: 0,
      date_basis: "UTC",
    });
  }
  if (group === "skills")
    return Object.entries(skillInfo).map(([name, info]) => ({
      name,
      description: info[2],
      category: info[3],
      approval: name === "media_generate",
      enabled: !state.settings.disabled_skills.includes(name),
    }));
  if (group === "models")
    return {
      ok: true,
      models: [find(state.settings.models, value, "Model").model],
      note: "Simulated connection. Preview never contacts model endpoints.",
    };
  if (group === "conversations") {
    if (!value && method === "GET") return clone(state.conversations);
    if (!value && method === "POST") {
      result = {
        id: id(),
        title: data.title || "New conversation",
        created: now(),
      };
      state.conversations.unshift(result);
      state.messages[result.id] = [];
    } else if (method === "GET") {
      find(state.conversations, value, "Conversation");
      result = {
        messages: state.messages[value] || [],
        runs: Object.values(state.runs)
          .filter((r) => r.conversation_id === value)
          .reverse(),
      };
    } else if (action === "chat") {
      if (
        Object.values(state.runs).some(
          (r) =>
            r.conversation_id === value &&
            ["queued", "running", "awaiting_approval"].includes(r.status),
        )
      )
        throw Error("This conversation already has an active task");
      const conv = find(state.conversations, value, "Conversation");
      if (!(state.messages[value] || []).length)
        conv.title = data.message.slice(0, 60);
      (state.messages[value] ||= []).push({
        id: id(),
        role: "user",
        content: data.message,
        created: now(),
      });
      result = {
        id: id(),
        conversation_id: value,
        status: "running",
        prompt: data.message,
        mode: data.mode,
        budget: data.budget_usd || 0.25,
        spent: 0,
        error: "",
        created: now(),
        ticks: 0,
        events: [
          { id: 1, kind: "status", data: { status: "running" } },
          {
            id: 2,
            kind: "model",
            data: { name: "Scripted preview", model: "Browser demo" },
          },
        ],
      };
      state.runs[result.id] = result;
    } else if (action === "upload") {
      const file = data.get("file");
      if (!file || file.size > 500000)
        throw Error(
          "Preview uploads support text files up to 500 KB. Use the Python app for PDFs and larger files.",
        );
      if (
        !/\.(txt|md|csv|json|py|html|obj|ya?ml|js|css|ics|eml)$/i.test(
          file.name,
        )
      )
        throw Error(
          "The preview supports text uploads. Use the Python app for PDFs.",
        );
      result = makeArtifact(
        { conversation_id: value, id: "" },
        file.name,
        file.type || "text/plain",
        await file.text(),
      );
    }
  } else if (group === "tasks") {
    if (!value && method === "GET")
      return clone(
        state.tasks
          .map((t) => ({
            ...t,
            run:
              Object.values(state.runs)
                .filter((r) => r.conversation_id === t.conversation_id)
                .at(-1) || null,
          }))
          .sort((a, b) => b.updated.localeCompare(a.updated)),
      );
    if (!value && method === "POST") {
      const conv = await demoRequest("/api/conversations", "POST", {
        title: data.title,
      });
      result = {
        ...data,
        id: id(),
        conversation_id: conv.id,
        status: "open",
        steps: [],
        created: now(),
        updated: now(),
      };
      state.tasks.unshift(result);
    } else if (action === "start") {
      const task = find(state.tasks, value, "Task");
      if (task.status === "done") throw Error("Reopen this task first");
      const run = await demoRequest(
        "/api/conversations/" + task.conversation_id + "/chat",
        "POST",
        {
          message: task.title + "\n\n" + task.objective,
          mode: data.mode || "economy",
        },
      );
      return {
        id: run.id,
        conversation_id: task.conversation_id,
        status: run.status,
      };
    } else if (method === "PATCH") {
      result = find(state.tasks, value, "Task");
      Object.assign(result, data, { updated: now() });
    }
  } else if (group === "runs") {
    result = state.runs[value];
    if (!result) throw Error("Run not found");
    if (action === "stop") {
      result.status = "cancelled";
      state.approvals
        .filter((a) => a.run_id === value && a.status === "pending")
        .forEach((a) => (a.status = "denied"));
    } else {
      if (["running", "queued"].includes(result.status) && ++result.ticks >= 2)
        finish(result);
      result = {
        ...result,
        events: result.events.filter(
          (e) => e.id > Number(url.searchParams.get("after") || 0),
        ),
        approvals: state.approvals.filter(
          (a) => a.run_id === value && a.status === "pending",
        ),
      };
    }
  } else if (group === "approvals") {
    const approval = find(state.approvals, value, "Approval");
    if (approval.status !== "pending")
      throw Error("This approval was already handled");
    approval.status = data.allow ? "approved" : "denied";
    const run = state.runs[approval.run_id];
    if (data.allow) finish(run, true);
    else {
      run.status = "completed";
      state.messages[run.conversation_id].push({
        role: "assistant",
        content:
          "The example generation was declined. No external request or charge was made.",
      });
    }
    result = { ok: true };
  } else if (group === "artifacts") {
    if (value && action === "download") {
      const a = find(state.artifacts, value, "File");
      return new Blob([a.content], { type: a.mime });
    }
    return clone(
      state.artifacts
        .filter(
          (a) =>
            !url.searchParams.get("conversation_id") ||
            a.conversation_id === url.searchParams.get("conversation_id"),
        )
        .map(({ content, ...a }) => a),
    );
  } else if (group === "media") return method === "GET" ? [] : { ok: true };
  else throw Error("This action is not available in the interactive preview.");
  save();
  return clone(result || { ok: true });
}
export function resetDemo() {
  state = seed();
  save();
}
