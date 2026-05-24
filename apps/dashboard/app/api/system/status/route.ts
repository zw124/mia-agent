import { existsSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";
import { currentUser } from "../../../../lib/auth";

export const runtime = "nodejs";

const root = process.cwd();

function envValue(name: string) {
  return process.env[name] || "";
}

function readHeartbeat() {
  const file = path.join(root, ".mia", "heartbeat.json");
  if (!existsSync(file)) return null;
  try {
    const stat = statSync(file);
    return {
      ...JSON.parse(readFileSync(file, "utf8")),
      updatedAt: stat.mtimeMs,
    };
  } catch {
    return null;
  }
}

function configured(value: string) {
  return Boolean(value && value !== "change-me");
}

export async function GET() {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }

  const heartbeat = readHeartbeat();
  const channels = [
    {
      id: "web",
      name: "Mia app",
      status: "online",
      detail: "Authenticated desktop and web app",
    },
    {
      id: "desktop",
      name: "Desktop companion",
      status: heartbeat ? heartbeat.status : "waiting",
      detail: heartbeat ? "Gateway heartbeat detected" : "Install and launch the companion",
    },
    {
      id: "message-relay",
      name: "Message relay",
      status:
        configured(envValue("SENDBLUE_API_KEY_ID")) &&
        configured(envValue("SENDBLUE_API_SECRET_KEY")) &&
        configured(envValue("SENDBLUE_FROM_NUMBER"))
          ? "ready"
          : "setup",
      detail: configured(envValue("SENDBLUE_FROM_NUMBER"))
        ? envValue("SENDBLUE_FROM_NUMBER")
        : "Optional external relay",
    },
  ];

  const services = [
    {
      id: "convex",
      name: "Convex",
      status: configured(envValue("NEXT_PUBLIC_CONVEX_URL")) ? "ready" : "setup",
      detail: envValue("NEXT_PUBLIC_CONVEX_URL") || "Missing NEXT_PUBLIC_CONVEX_URL",
    },
    {
      id: "agent",
      name: "Agent service",
      status: heartbeat?.checks?.fastapi?.ok ? "online" : "waiting",
      detail: envValue("AGENT_SERVICE_URL") || "http://localhost:8000",
    },
    {
      id: "model",
      name: "Model endpoint",
      status:
        configured(envValue("OPENAI_API_KEY")) &&
        configured(envValue("OPENAI_BASE_URL")) &&
        configured(envValue("MODEL_NAME"))
          ? "ready"
          : "setup",
      detail: envValue("MODEL_NAME") || "Missing MODEL_NAME",
    },
    {
      id: "search",
      name: "Search",
      status: configured(envValue("SEARXNG_BASE_URL")) ? "ready" : "optional",
      detail: envValue("SEARXNG_BASE_URL") || "SearXNG optional",
    },
  ];

  const install = {
    mac: "npm run mia:gateway:install",
    windows: "npm run desktop:dev --workspace apps/desktop",
    linux: "npm run desktop:dev --workspace apps/desktop",
  };

  return NextResponse.json({
    ok: true,
    user,
    heartbeat,
    channels,
    services,
    install,
    updatedAt: Date.now(),
  });
}
