(() => {
  let theme = "system";
  try {
    theme = localStorage.getItem("static-theme") || "system";
  } catch {
    /* Private browsing */
  }
  const system = matchMedia("(prefers-color-scheme: dark)");
  const apply = () => {
    document.documentElement.dataset.theme =
      theme === "system" ? (system.matches ? "dark" : "light") : theme;
    document.querySelector('meta[name="theme-color"]').content =
      document.documentElement.dataset.theme === "dark" ? "#151619" : "#f7f8fa";
    window.dispatchEvent(new Event("static-theme"));
  };
  window.staticTheme = {
    get: () => theme,
    set: (next) => {
      theme = ["light", "dark", "system"].includes(next) ? next : "system";
      try {
        localStorage.setItem("static-theme", theme);
      } catch {}
      apply();
    },
  };
  system.addEventListener("change", apply);
  apply();
})();
