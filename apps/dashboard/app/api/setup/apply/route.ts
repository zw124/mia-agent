import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

const root = process.cwd();

type SetupPayload = {
  envText?: string;
  convexUrl?: string;
};

function parseEnv(text: string) {
  const values = new Map<string, string>();
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator < 1) continue;
    values.set(trimmed.slice(0, separator), trimmed.slice(separator + 1));
  }
  return values;
}

function readEnv(filePath: string) {
  if (!existsSync(filePath)) return new Map<string, string>();
  return parseEnv(readFileSync(filePath, "utf8"));
}

function serializeEnv(values: Map<string, string>) {
  return `${Array.from(values.entries()).map(([key, value]) => `${key}=${value}`).join("\n")}\n`;
}

function mergeEnv(existing: Map<string, string>, incomingText: string) {
  const incoming = parseEnv(incomingText);
  const merged = new Map(existing);

  for (const [key, value] of incoming) {
    const hasExisting = existing.has(key) && existing.get(key) !== "";
    if (value === "" && hasExisting) continue;
    if (key === "MIA_INTERNAL_SECRET" && value === "change-me" && hasExisting) continue;
    merged.set(key, value);
  }

  return merged;
}

export async function POST(request: Request) {
  const body = (await request.json()) as SetupPayload;
  const envText = body.envText?.trim();
  if (!envText) {
    return NextResponse.json({ ok: false, error: "Missing envText" }, { status: 400 });
  }

  const rootEnv = path.join(root, ".env.local");
  const dashboardEnv = path.join(root, "apps", "dashboard", ".env.local");
  const agentEnv = path.join(root, "apps", "agent-service", ".env");
  mkdirSync(path.dirname(dashboardEnv), { recursive: true });
  mkdirSync(path.dirname(agentEnv), { recursive: true });

  writeFileSync(rootEnv, serializeEnv(mergeEnv(readEnv(rootEnv), envText)));
  writeFileSync(agentEnv, serializeEnv(mergeEnv(readEnv(agentEnv), envText)));
  if (body.convexUrl) {
    writeFileSync(dashboardEnv, `NEXT_PUBLIC_CONVEX_URL=${body.convexUrl}\n`);
  }

  return NextResponse.json({
    ok: true,
    written: [rootEnv, agentEnv, body.convexUrl ? dashboardEnv : null].filter(Boolean),
  });
}
