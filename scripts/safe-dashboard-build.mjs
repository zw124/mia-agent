#!/usr/bin/env node

import { spawnSync } from "node:child_process";

const ps = spawnSync("ps", ["-axo", "pid=,command="], { encoding: "utf8" });
if (ps.status !== 0) {
  process.stderr.write(ps.stderr || "Could not inspect running processes.\n");
  process.exit(ps.status ?? 1);
}

const runningDashboardDev = ps.stdout
  .split("\n")
  .filter((line) => line.includes("next-server") || line.includes("next dev apps/dashboard"))
  .filter((line) => !line.includes("safe-dashboard-build"));

if (runningDashboardDev.length > 0) {
  process.stderr.write(
    [
      "Refusing to build while the dashboard dev server is running.",
      "Stop the desktop app / gateway first, then run npm run build again.",
      "",
      "Running process(es):",
      ...runningDashboardDev,
      "",
    ].join("\n"),
  );
  process.exit(1);
}

const build = spawnSync("npx", ["next", "build", "apps/dashboard"], {
  stdio: "inherit",
  shell: false,
});

process.exit(build.status ?? 1);
