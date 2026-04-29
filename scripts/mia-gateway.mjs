#!/usr/bin/env node

import { createWriteStream, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const logsDir = path.join(root, ".mia", "logs");
mkdirSync(logsDir, { recursive: true });

const args = new Set(process.argv.slice(2));
const getArgValue = (name, fallback = "") => {
  const raw = process.argv.find((arg) => arg.startsWith(`${name}=`));
  return raw ? raw.slice(name.length + 1) : fallback;
};

if (args.has("--help") || args.has("-h")) {
  console.log(`Mia Gateway

Usage:
  npm run mia:gateway
  npm run mia:gateway:localtunnel
  npm run mia:gateway:ngrok
  node scripts/mia-gateway.mjs [options]

Options:
  --no-convex              Do not start Convex dev
  --no-dashboard           Do not start Next.js dashboard
  --no-agent               Do not start FastAPI agent service
  --tunnel=localtunnel     Start localtunnel for the agent service
  --tunnel=ngrok           Start ngrok for the agent service
  --dashboard-port=3000    Dashboard port
  --agent-port=8000        Agent service port
  --heartbeat-ms=120000    Heartbeat interval clamped to 1-5 minutes
  --no-heartbeat           Disable system heartbeat
  --verbose                Stream child process output in this terminal
`);
  process.exit(0);
}

const dashboardPort = Number(getArgValue("--dashboard-port", "3000"));
const agentPort = Number(getArgValue("--agent-port", "8000"));
const verbose = args.has("--verbose");
const heartbeatMs = Math.max(
  60_000,
  Math.min(300_000, Number(getArgValue("--heartbeat-ms", "120000")) || 120_000),
);
const heartbeatEnabled = !args.has("--no-heartbeat");
const heartbeatFile = path.join(root, ".mia", "heartbeat.json");

const basePath = [
  path.join(root, ".venv", "bin"),
  "/opt/homebrew/bin",
  "/usr/local/bin",
  "/usr/bin",
  "/bin",
  "/usr/sbin",
  "/sbin",
  process.env.PATH ?? "",
].join(":");

const children = new Map();
const managedServices = new Map();

function loadEnvFile(filePath) {
  if (!existsSync(filePath)) return {};
  const env = {};
  const text = readFileSync(filePath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const index = trimmed.indexOf("=");
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

const fileEnv = {
  ...loadEnvFile(path.join(root, ".env")),
  ...loadEnvFile(path.join(root, ".env.local")),
  ...loadEnvFile(path.join(root, "apps", "agent-service", ".env")),
  ...loadEnvFile(path.join(root, "apps", "dashboard", ".env.local")),
};

const runtimeEnv = { ...fileEnv, ...process.env, PATH: basePath };
const configuredAgentServiceUrl = String(runtimeEnv.AGENT_SERVICE_URL ?? "").replace(/\/$/, "");
const requestedTunnel = getArgValue("--tunnel", args.has("--ngrok") ? "ngrok" : "");
const tunnel =
  requestedTunnel ||
  (configuredAgentServiceUrl && configuredAgentServiceUrl.includes(".loca.lt")
    ? "localtunnel"
    : "");

function logLine(service, line) {
  process.stdout.write(`[${service}] ${line}`);
}

function makeLog(service) {
  return createWriteStream(path.join(logsDir, `${service}.log`), { flags: "a" });
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host: "127.0.0.1" });
    socket.setTimeout(500);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => resolve(false));
  });
}

function commandExists(command) {
  return new Promise((resolve) => {
    const child = spawn("sh", ["-lc", `command -v ${command}`], {
      cwd: root,
      env: { ...process.env, PATH: basePath },
      stdio: "ignore",
    });
    child.once("exit", (code) => resolve(code === 0));
  });
}

function spawnService({ name, command, args: serviceArgs, cwd = root, env = {} }) {
  const log = makeLog(name);
  log.write(`\n\n=== ${new Date().toISOString()} starting ${name} ===\n`);
  const child = spawn(command, serviceArgs, {
    cwd,
    env: { ...runtimeEnv, ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  children.set(name, child);
  managedServices.set(name, { name, command, args: serviceArgs, cwd, env });

  child.stdout.on("data", (chunk) => {
    const text = chunk.toString();
    log.write(text);
    if (verbose) {
      for (const line of text.split(/(?<=\n)/)) {
        if (line) logLine(name, line);
      }
    }
  });

  child.stderr.on("data", (chunk) => {
    const text = chunk.toString();
    log.write(text);
    if (verbose) {
      for (const line of text.split(/(?<=\n)/)) {
        if (line) logLine(name, line);
      }
    }
  });

  child.once("exit", (code, signal) => {
    children.delete(name);
    const line = `exited code=${code ?? "null"} signal=${signal ?? "none"}\n`;
    log.write(line);
    log.end();
    logLine("gateway", `${name} ${line}`);
  });
}

function localtunnelArgs() {
  const serviceArgs = ["--yes", "localtunnel", "--port", String(agentPort)];
  if (configuredAgentServiceUrl) {
    try {
      const host = new URL(configuredAgentServiceUrl).hostname;
      if (host.endsWith(".loca.lt")) {
        serviceArgs.push("--subdomain", host.slice(0, -".loca.lt".length));
      }
    } catch {
      // localtunnel will allocate a random URL when AGENT_SERVICE_URL is not parseable.
    }
  }
  return serviceArgs;
}

async function fetchJson(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? 5000);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.headers ?? {}),
      },
    });
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { text };
    }
    return { ok: response.ok, status: response.status, data };
  } finally {
    clearTimeout(timer);
  }
}

async function restartManagedService(name, reason) {
  const spec = managedServices.get(name);
  if (!spec) return `cannot restart ${name}: not managed by this gateway`;
  const existing = children.get(name);
  if (existing && existing.exitCode === null) {
    existing.kill("SIGTERM");
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  spawnService(spec);
  return `restarted ${name}: ${reason}`;
}

async function runHeartbeat() {
  const checks = {};
  const repairs = [];
  const startedAt = new Date().toISOString();

  try {
    const health = await fetchJson(`http://127.0.0.1:${agentPort}/health`, { timeoutMs: 5000 });
    checks.fastapi = health;
    if (!health.ok && !args.has("--no-agent")) {
      repairs.push(await restartManagedService("agent", `health status ${health.status}`));
    }
  } catch (error) {
    checks.fastapi = { ok: false, error: error instanceof Error ? error.message : String(error) };
    if (!args.has("--no-agent")) {
      repairs.push(await restartManagedService("agent", "health request failed"));
    }
  }

  if (configuredAgentServiceUrl) {
    try {
      const publicHealth = await fetchJson(`${configuredAgentServiceUrl}/health`, {
        timeoutMs: 15000,
      });
      checks.publicAgent = {
        ok: publicHealth.ok,
        status: publicHealth.status,
        url: configuredAgentServiceUrl,
      };
      if (!publicHealth.ok && tunnel) {
        repairs.push(
          await restartManagedService(tunnel === "localtunnel" ? "localtunnel" : "ngrok", `public agent status ${publicHealth.status}`),
        );
      }
    } catch (error) {
      checks.publicAgent = {
        ok: false,
        url: configuredAgentServiceUrl,
        error: error instanceof Error ? error.message : String(error),
      };
      if (tunnel) {
        repairs.push(
          await restartManagedService(tunnel === "localtunnel" ? "localtunnel" : "ngrok", "public agent health failed"),
        );
      }
    }
  } else {
    checks.publicAgent = {
      ok: false,
      skipped: true,
      reason: "AGENT_SERVICE_URL is not configured",
    };
  }

  try {
    const dashboardAlive = await isPortOpen(dashboardPort);
    checks.dashboard = { ok: dashboardAlive, port: dashboardPort };
    if (!dashboardAlive && !args.has("--no-dashboard")) {
      repairs.push(await restartManagedService("dashboard", "dashboard port closed"));
    }
  } catch (error) {
    checks.dashboard = { ok: false, error: error instanceof Error ? error.message : String(error) };
  }

  try {
    checks.gateway = {
      ok: true,
      pid: process.pid,
      managedChildren: Array.from(children.keys()),
      heartbeatMs,
    };
  } catch (error) {
    checks.gateway = { ok: false, error: error instanceof Error ? error.message : String(error) };
  }

  if (tunnel === "ngrok") {
    try {
      const ngrokAlive = await isPortOpen(4040);
      checks.openclawGateway = { ok: ngrokAlive, kind: "ngrok", localPort: 4040 };
      if (!ngrokAlive) repairs.push(await restartManagedService("ngrok", "ngrok web UI closed"));
    } catch (error) {
      checks.openclawGateway = {
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  } else {
    checks.openclawGateway = {
      ok: false,
      skipped: true,
      reason: "No ngrok gateway process requested by this Mia gateway.",
    };
  }

  const convexSiteUrl = runtimeEnv.CONVEX_SITE_URL;
  const internalSecret = runtimeEnv.MIA_INTERNAL_SECRET;
  if (convexSiteUrl && internalSecret) {
    try {
      const repair = await fetchJson(`${convexSiteUrl.replace(/\/$/, "")}/internal/heartbeat/repair`, {
        method: "POST",
        timeoutMs: 15000,
        headers: {
          "content-type": "application/json",
          "x-mia-internal-secret": internalSecret,
        },
        body: JSON.stringify({ maxRunAgeMs: 15 * 60 * 1000 }),
      });
      checks.convex = { ok: repair.ok, repair };
      const result = repair.data?.result ?? repair.data;
      const staleCount = result?.staleRuns?.repaired ?? 0;
      const expiredCount = result?.expiredApprovals?.expired ?? 0;
      if (staleCount > 0) repairs.push(`marked ${staleCount} stale run(s) failed`);
      if (expiredCount > 0) repairs.push(`expired ${expiredCount} pending approval(s)`);
    } catch (error) {
      checks.convex = { ok: false, error: error instanceof Error ? error.message : String(error) };
      if (!args.has("--no-convex")) repairs.push(await restartManagedService("convex", "Convex HTTP failed"));
    }
  } else {
    checks.convex = {
      ok: false,
      skipped: true,
      reason: "CONVEX_SITE_URL or MIA_INTERNAL_SECRET is missing",
    };
  }

  const status = Object.values(checks).every((check) => check?.ok === true || check?.skipped)
    ? "ok"
    : repairs.length > 0
      ? "degraded"
      : "failed";

  const heartbeat = { source: "mia-gateway", status, checks, repairs, startedAt, completedAt: new Date().toISOString() };
  writeFileSync(heartbeatFile, JSON.stringify(heartbeat, null, 2));

  if (convexSiteUrl && internalSecret) {
    try {
      await fetchJson(`${convexSiteUrl.replace(/\/$/, "")}/internal/heartbeat/record`, {
        method: "POST",
        timeoutMs: 10000,
        headers: {
          "content-type": "application/json",
          "x-mia-internal-secret": internalSecret,
        },
        body: JSON.stringify({
          source: heartbeat.source,
          status: heartbeat.status,
          checks: heartbeat.checks,
          repairs: heartbeat.repairs,
        }),
      });
    } catch {
      // Local heartbeat file is the fallback when Convex cannot be reached.
    }
  }

  if (verbose || status !== "ok" || repairs.length > 0) {
    logLine("heartbeat", `${status}${repairs.length ? ` repairs=${repairs.join("; ")}` : ""}\n`);
  }
}

function startHeartbeatLoop() {
  if (!heartbeatEnabled) {
    logLine("heartbeat", "disabled\n");
    return;
  }
  logLine("heartbeat", `every ${heartbeatMs}ms; state ${heartbeatFile}\n`);
  setTimeout(() => runHeartbeat().catch((error) => logLine("heartbeat", `${error.stack ?? error}\n`)), 5000).unref();
  setInterval(
    () => runHeartbeat().catch((error) => logLine("heartbeat", `${error.stack ?? error}\n`)),
    heartbeatMs,
  ).unref();
}

function printBanner() {
  process.stdout.write(`
███╗   ███╗██╗ █████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗
████╗ ████║██║██╔══██╗    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
██╔████╔██║██║███████║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
██║╚██╔╝██║██║██╔══██║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
██║ ╚═╝ ██║██║██║  ██║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
╚═╝     ╚═╝╚═╝╚═╝  ╚═╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝

`);
}

async function start() {
  printBanner();
  logLine("gateway", `root ${root}\n`);
  logLine("gateway", `logs ${logsDir}\n`);

  if (!args.has("--no-convex")) {
    spawnService({
      name: "convex",
      command: "npx",
      args: ["convex", "dev"],
    });
  }

  if (!args.has("--no-dashboard")) {
    if (await isPortOpen(dashboardPort)) {
      logLine("dashboard", `port ${dashboardPort} already listening; not starting duplicate\n`);
    } else {
      spawnService({
        name: "dashboard",
        command: "npx",
        args: ["next", "dev", "apps/dashboard", "-p", String(dashboardPort)],
      });
    }
  }

  if (!args.has("--no-agent")) {
    if (await isPortOpen(agentPort)) {
      logLine("agent", `port ${agentPort} already listening; not starting duplicate\n`);
    } else {
      const uvicorn = path.join(root, ".venv", "bin", "uvicorn");
      spawnService({
        name: "agent",
        command: existsSync(uvicorn) ? uvicorn : "uvicorn",
        args: ["mia.main:app", "--reload", "--port", String(agentPort)],
        cwd: path.join(root, "apps", "agent-service"),
      });
    }
  }

  if (tunnel === "ngrok") {
    if (await commandExists("ngrok")) {
      spawnService({
        name: "ngrok",
        command: "ngrok",
        args: ["http", String(agentPort)],
      });
    } else {
      logLine("ngrok", "ngrok is not installed or not on PATH; tunnel skipped\n");
    }
  } else if (tunnel === "localtunnel") {
    spawnService({
      name: "localtunnel",
      command: "npx",
      args: localtunnelArgs(),
    });
  }

  logLine("gateway", `dashboard http://localhost:${dashboardPort}\n`);
  logLine("gateway", `agent http://localhost:${agentPort}/health\n`);
  if (configuredAgentServiceUrl) {
    logLine("gateway", `public agent ${configuredAgentServiceUrl}/health\n`);
  }
  logLine("gateway", "child output is in .mia/logs; use --verbose to stream it here\n");
  startHeartbeatLoop();
}

function shutdown(signal) {
  logLine("gateway", `received ${signal}; stopping ${children.size} child service(s)\n`);
  for (const [name, child] of children) {
    logLine("gateway", `stopping ${name}\n`);
    child.kill("SIGTERM");
  }
  setTimeout(() => process.exit(0), 1200).unref();
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

start().catch((error) => {
  logLine("gateway", `${error instanceof Error ? error.stack : String(error)}\n`);
  process.exit(1);
});
