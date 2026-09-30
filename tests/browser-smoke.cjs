// End-to-end tests for the actual Python UI and the standalone Pages preview.
// The live fixture uses an isolated deterministic provider; no paid APIs are called.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require(
  process.env.STATIC_PLAYWRIGHT_PATH || "playwright",
);
const live = process.env.STATIC_TEST_URL || "http://127.0.0.1:8765";
const preview =
  process.env.STATIC_PREVIEW_URL || "http://127.0.0.1:8766/Static";
async function ready(url) {
  for (let i = 0; i < 60; i++) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  throw Error("Test server unavailable: " + url);
}
async function waitPage(page) {
  await page.locator("#main h1").waitFor();
}
(async () => {
  await Promise.all([
    ready(live + "/api/health"),
    ready(preview + "/index.html"),
  ]);
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.STATIC_CHROMIUM_PATH || undefined,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  fs.mkdirSync("test-results", { recursive: true });
  try {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1040 },
      acceptDownloads: true,
    });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(live);
    await waitPage(page);
    assert.match(await page.title(), /Static/);
    assert.equal(await page.locator("#preview-badge").isVisible(), false);
    await page.locator('nav a[data-page="connections"]').click();
    await page.locator(".model-card > summary").click();
    await page
      .getByRole("button", { name: "Test connection", exact: true })
      .click();
    await page.waitForFunction(
      () =>
        document.querySelector(".model-actions>span").textContent ===
        "Connected",
    );
    await page.locator('nav a[data-page="skills"]').click();
    await page.locator(".skill-card").first().waitFor();
    assert.equal(await page.locator(".skill-card").count(), 13);
    const mesh = page.getByRole("checkbox", {
      name: "Enable 3D shapes",
      exact: true,
    });
    await mesh.uncheck();
    await page.waitForFunction(
      () => document.querySelector("#toast").textContent === "Skill updated",
    );
    await page.reload();
    await page.locator(".skill-card").first().waitFor();
    assert.equal(await mesh.isChecked(), false);
    await mesh.check();
    await page
      .getByRole("button", { name: "New conversation", exact: false })
      .first()
      .click();
    await page
      .locator("#prompt")
      .fill("Create a project plan as a Markdown file.");
    await page.locator("#send").click();
    await page.locator(".message.assistant a").waitFor();
    const downloadPromise = page.waitForEvent("download");
    await page.locator(".message.assistant a").click();
    const download = await downloadPromise;
    assert.match(
      fs.readFileSync(await download.path(), "utf8"),
      /# Project plan/,
    );
    const chatURL = page.url();
    await page.reload();
    await page.locator(".message.assistant").waitFor();
    assert.equal(page.url(), chatURL);
    assert.equal(await page.locator(".message").count(), 2);
    await page.locator('nav a[data-page="library"]').click();
    await page.locator(".file-card").waitFor();
    assert.match(
      await page.locator(".file-card").innerText(),
      /project-plan.md/,
    );
    await page.locator('nav a[data-page="tasks"]').click();
    await page
      .getByRole("button", { name: "New task", exact: true })
      .first()
      .click();
    await page.getByLabel("Task name", { exact: true }).fill("Launch Static");
    await page
      .getByLabel("What would you like to accomplish?", { exact: true })
      .fill("Create a concise project plan.");
    await page.getByRole("button", { name: "Save task", exact: true }).click();
    await page.locator(".task-card").waitFor();
    await page.getByRole("button", { name: "Open task", exact: true }).click();
    await page
      .getByRole("button", { name: "Work on this", exact: true })
      .click();
    await page.locator(".message.assistant a").waitFor();
    await page.locator('nav a[data-page="home"]').click();
    await waitPage(page);
    await page.screenshot({
      path: "test-results/static-live.png",
      fullPage: true,
    });
    assert.deepEqual(errors, [], "Live JavaScript errors");
    await page.close();

    const demo = await browser.newPage({
      viewport: { width: 1440, height: 1040 },
      acceptDownloads: true,
    });
    const demoErrors = [],
      forbiddenRequests = [];
    demo.on("pageerror", (e) => demoErrors.push(e.message));
    demo.on("request", (r) => {
      if (
        new URL(r.url()).pathname.startsWith("/api/") ||
        !r.url().startsWith("http://127.0.0.1:8766/")
      )
        forbiddenRequests.push(r.url());
    });
    await demo.goto(preview + "/index.html");
    await waitPage(demo);
    assert.equal(await demo.locator("#preview-badge").isVisible(), true);
    assert.equal(await demo.locator(".task-row").count(), 3);
    await demo.screenshot({
      path: "test-results/static-light.png",
      fullPage: true,
    });
    await demo
      .getByRole("button", { name: "Switch to dark mode", exact: true })
      .click();
    assert.equal(await demo.locator("html").getAttribute("data-theme"), "dark");
    await demo.reload();
    await waitPage(demo);
    assert.equal(await demo.locator("html").getAttribute("data-theme"), "dark");
    await demo.screenshot({
      path: "test-results/static-dark.png",
      fullPage: true,
    });
    await demo
      .getByRole("button", { name: "Switch to light mode", exact: true })
      .click();
    // Real entry points must survive direct navigation and reload under a repo subpath.
    for (const route of [
      "tasks",
      "create",
      "library",
      "skills",
      "connections",
      "settings",
      "chat",
    ]) {
      await demo.goto(preview + "/" + route + ".html");
      await waitPage(demo);
      await demo.reload();
      await waitPage(demo);
      assert(
        !(await demo.locator(".notice.error").count()),
        route + " page failed",
      );
    }
    await demo.goto(preview + "/tasks.html");
    await waitPage(demo);
    await demo
      .getByRole("button", { name: "New task", exact: true })
      .first()
      .click();
    await demo.getByLabel("Task name", { exact: true }).fill("My preview goal");
    await demo
      .getByLabel("What would you like to accomplish?", { exact: true })
      .fill("Make a small launch checklist.");
    await demo.getByRole("button", { name: "Save task", exact: true }).click();
    await demo
      .getByRole("heading", { name: "My preview goal", exact: true })
      .waitFor();
    await demo.reload();
    await waitPage(demo);
    const taskCard = demo
      .locator(".task-card")
      .filter({ hasText: "My preview goal" });
    await taskCard
      .getByRole("button", { name: "Open task", exact: true })
      .click();
    await demo
      .getByRole("button", { name: "Mark complete", exact: true })
      .click();
    await demo.getByRole("button", { name: "Completed", exact: true }).click();
    await demo
      .getByRole("heading", { name: "My preview goal", exact: true })
      .waitFor();
    await demo.goto(preview + "/create.html");
    await waitPage(demo);
    await demo.getByRole("button", { name: "Image", exact: true }).click();
    await demo
      .getByLabel("Your idea", { exact: true })
      .fill("An abstract image in lavender");
    await demo
      .getByRole("button", { name: "Try an example", exact: true })
      .click();
    await demo
      .getByRole("button", { name: "Approve example", exact: true })
      .waitFor();
    await demo
      .getByRole("button", { name: "Approve example", exact: true })
      .click();
    await demo.locator(".message.assistant a").waitFor();
    const exampleDownload = demo.waitForEvent("download");
    await demo.locator(".message.assistant a").click();
    assert.match(
      fs.readFileSync(await (await exampleDownload).path(), "utf8"),
      /<svg/,
    );
    await demo.goto(preview + "/library.html");
    await waitPage(demo);
    assert((await demo.locator(".file-card").count()) >= 4);
    await demo.getByRole("button", { name: "Documents", exact: true }).click();
    await demo
      .locator(".file-card")
      .first()
      .getByRole("button", { name: "Open", exact: true })
      .click();
    await demo.locator("#modal pre").waitFor();
    assert.match(await demo.locator("#modal pre").innerText(), /checklist/);
    await demo
      .getByRole("button", { name: "Close dialog", exact: true })
      .click();
    await demo.goto(preview + "/skills.html");
    await waitPage(demo);
    await demo
      .getByRole("checkbox", { name: "Enable Email drafts", exact: true })
      .uncheck();
    await demo.waitForFunction(() =>
      document.querySelector("#toast").textContent.includes("Skill updated"),
    );
    await demo.reload();
    await waitPage(demo);
    assert.equal(
      await demo
        .getByRole("checkbox", { name: "Enable Email drafts", exact: true })
        .isChecked(),
      false,
    );
    await demo.goto(preview + "/settings.html");
    await waitPage(demo);
    await demo
      .getByLabel("What should we call you?", { exact: true })
      .fill("Casey");
    await demo
      .getByRole("button", { name: "Save preferences", exact: true })
      .click();
    await demo.waitForFunction(
      () => document.querySelector("#profile-name").textContent === "Casey",
    );
    await demo.reload();
    await waitPage(demo);
    assert.equal(
      await demo
        .getByLabel("What should we call you?", { exact: true })
        .inputValue(),
      "Casey",
    );
    await demo
      .getByRole("button", {
        name: "Search conversations and tasks",
        exact: true,
      })
      .click();
    await demo
      .getByRole("searchbox", { name: "Search your workspace…", exact: true })
      .fill("My preview goal");
    assert((await demo.locator(".search-result").count()) >= 1);
    await demo
      .getByRole("button", { name: "Close dialog", exact: true })
      .click();
    // User content is rendered as text, including hostile markup.
    await demo.locator("#new-chat").click();
    await demo.locator("#prompt").fill('<img src=x onerror="window.hacked=1">');
    await demo.locator("#send").click();
    await demo.locator(".message.assistant").waitFor();
    assert.equal(await demo.locator(".message.user img").count(), 0);
    // Mobile layout on every real page, including forms and both themes.
    await demo.setViewportSize({ width: 390, height: 844 });
    for (const theme of ["light", "dark"]) {
      if ((await demo.locator("html").getAttribute("data-theme")) !== theme) {
        await demo.locator("#menu").click();
        await demo.locator("#theme-toggle").click();
        await demo
          .locator("#sidebar-shade")
          .click({ position: { x: 350, y: 30 } });
      }
      for (const route of [
        "index",
        "tasks",
        "create",
        "library",
        "skills",
        "connections",
        "settings",
        "chat",
      ]) {
        await demo.goto(preview + "/" + route + ".html");
        await waitPage(demo);
        assert.equal(
          await demo.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
          route + " overflow in " + theme,
        );
        if (route === "index")
          await demo.screenshot({
            path: "test-results/static-mobile-" + theme + ".png",
            fullPage: true,
          });
      }
    }
    await demo.locator("#menu").click();
    await demo.locator('nav a[data-page="tasks"]').click();
    await waitPage(demo);
    assert.equal(
      await demo.locator("#menu").getAttribute("aria-expanded"),
      "false",
    );
    assert.deepEqual(demoErrors, [], "Preview JavaScript errors");
    assert.deepEqual(
      forbiddenRequests,
      [],
      "Preview must never send network/API requests outside its static assets",
    );
    for (const [label, base] of [
      ["live", live],
      ["preview", preview],
    ]) {
      const miniContext = await browser.newContext({
        viewport: { width: 440, height: 640 },
        acceptDownloads: true,
      });
      const mini = await miniContext.newPage();
      const miniErrors = [];
      const miniRequests = [];
      mini.on("pageerror", (e) => miniErrors.push(e.message));
      mini.on("request", (request) => {
        if (
          label === "preview" &&
          (request.url().includes("/api/") ||
            !request.url().startsWith(base + "/"))
        )
          miniRequests.push(request.url());
      });
      await mini.goto(base + "/mini.html");
      await mini.locator(".mini-empty h1").waitFor();
      await mini
        .locator("#mini-prompt")
        .fill("Create a project plan as a Markdown file.");
      await mini.locator("#mini-prompt").press("Enter");
      await mini.locator(".mini-message.assistant").waitFor();
      const fullURL = await mini.locator("#mini-open").getAttribute("href");
      assert.match(fullURL, /chat\.html\?id=/);
      await mini.reload();
      await mini.locator(".mini-message.assistant").waitFor();
      assert.equal(await mini.locator(".mini-message.user").count(), 1);
      for (const theme of ["light", "dark"]) {
        await mini.evaluate((t) => window.staticTheme.set(t), theme);
        assert.equal(
          await mini.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );
        if (label === "preview")
          await mini.screenshot({
            path: "test-results/static-quick-chat-" + theme + ".png",
          });
      }
      const full = await mini.context().newPage();
      await full.goto(new URL(fullURL, base + "/mini.html").href);
      await full.locator(".message.assistant").waitFor();
      await full.close();
      await mini.locator("#mini-new").click();
      await mini.locator(".mini-empty h1").waitFor();
      assert.deepEqual(miniErrors, [], "Quick chat JavaScript errors");
      assert.deepEqual(
        miniRequests,
        [],
        "Quick chat preview API/network requests",
      );
      await mini.close();
      await miniContext.close();
    }
    console.log(
      "Browser checks passed: live model settings, 13 skills, file generation/download, persistent chats/tasks, eight Pages routes, approvals, preview persistence, no API calls, light/dark themes, mobile layout, safe rendering and live/preview quick chat.",
    );
    await demo.close();
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
