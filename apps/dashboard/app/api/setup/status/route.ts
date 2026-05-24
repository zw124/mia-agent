import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

const root = process.cwd();

function parseEnv(text: string) {
  const values = new Map<string, string>();
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator < 1) continue;
    let value = trimmed.slice(separator + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    values.set(trimmed.slice(0, separator).trim(), value);
  }
  return values;
}

function readEnv(filePath: string) {
  if (!existsSync(filePath)) return new Map<string, string>();
  return parseEnv(readFileSync(filePath, "utf8"));
}

export async function GET() {
  const envFile = path.join(root, ".env.local");
  const envLocalMap = readEnv(envFile);

  const agentEnvFile = path.join(root, "apps", "agent-service", ".env");
  const agentEnvMap = readEnv(agentEnvFile);

  // Combine, preferring root .env.local
  const combined = new Map([...agentEnvMap.entries(), ...envLocalMap.entries()]);

  const config = {
    openaiApiKey: combined.get("OPENAI_API_KEY") || "",
    openaiBaseUrl: combined.get("OPENAI_BASE_URL") || "https://api.openai.com/v1",
    modelName: combined.get("MODEL_NAME") || "gpt-4o-mini",
    agentServiceUrl: combined.get("AGENT_SERVICE_URL") || "http://localhost:8000",
    sendblueApiKeyId: combined.get("SENDBLUE_API_KEY_ID") || "",
    sendblueSecretKey: combined.get("SENDBLUE_API_SECRET_KEY") || "",
    sendblueFromNumber: combined.get("SENDBLUE_FROM_NUMBER") || "",
    ownerPhoneNumber: combined.get("OWNER_PHONE_NUMBER") || "",
    telegramBotToken: combined.get("TELEGRAM_BOT_TOKEN") || "",
    telegramOwnerChatId: combined.get("TELEGRAM_OWNER_CHAT_ID") || "",
    composioEnabled: combined.get("COMPOSIO_ENABLED") === "true",
    convexUrl: process.env.NEXT_PUBLIC_CONVEX_URL || combined.get("NEXT_PUBLIC_CONVEX_URL") || "",
  };

  return NextResponse.json({
    ok: true,
    root,
    envLocalExists: existsSync(envFile),
    agentEnvExists: existsSync(agentEnvFile),
    convexInstalled: existsSync(path.join(root, "node_modules", "convex")),
    gatewayInstalled: existsSync(path.join(root, "scripts", "mia-gateway.mjs")),
    dashboardEnvExists: existsSync(path.join(root, "apps", "dashboard", ".env.local")),
    config,
  });
}

