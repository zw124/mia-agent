#!/usr/bin/env node

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const envPath = path.join(root, ".env.local");

const rl = readline.createInterface({ input, output });

function readEnv(filePath) {
  if (!existsSync(filePath)) return {};
  const env = {};
  for (const line of readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const index = trimmed.indexOf("=");
    env[trimmed.slice(0, index)] = trimmed.slice(index + 1);
  }
  return env;
}

function serializeEnv(env) {
  const groups = [
    ["# Model", "OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_NAME", "TRANSCRIPTION_MODEL"],
    [
      "# Convex / Gateway",
      "CONVEX_URL",
      "CONVEX_SITE_URL",
      "NEXT_PUBLIC_CONVEX_URL",
      "AGENT_SERVICE_URL",
      "MIA_INTERNAL_SECRET",
    ],
    [
      "# SendBlue iMessage",
      "SENDBLUE_API_KEY_ID",
      "SENDBLUE_API_SECRET_KEY",
      "SENDBLUE_FROM_NUMBER",
      "SENDBLUE_WEBHOOK_SECRET",
      "SENDBLUE_STATUS_CALLBACK",
      "OWNER_PHONE_NUMBER",
    ],
    [
      "# Telegram",
      "TELEGRAM_BOT_TOKEN",
      "TELEGRAM_WEBHOOK_SECRET",
      "TELEGRAM_OWNER_CHAT_ID",
      "TELEGRAM_ALLOWED_CHAT_IDS",
    ],
    ["# Search / Composio", "SEARXNG_BASE_URL", "COMPOSIO_ENABLED"],
    ["# Web login", "MIA_WEB_ADMIN_EMAIL", "MIA_WEB_ADMIN_PASSWORD", "MIA_WEB_AUTH_SECRET"],
  ];
  const emitted = new Set();
  const lines = [];
  for (const group of groups) {
    lines.push(group[0]);
    for (const key of group.slice(1)) {
      emitted.add(key);
      lines.push(`${key}=${env[key] ?? ""}`);
    }
    lines.push("");
  }
  for (const [key, value] of Object.entries(env)) {
    if (!emitted.has(key)) lines.push(`${key}=${value}`);
  }
  return `${lines.join("\n").trim()}\n`;
}

async function ask(question, fallback = "") {
  const suffix = fallback ? ` (${fallback})` : "";
  const answer = (await rl.question(`${question}${suffix}: `)).trim();
  return answer || fallback;
}

async function yes(question, fallback = true) {
  const hint = fallback ? "Y/n" : "y/N";
  const answer = (await rl.question(`${question} [${hint}]: `)).trim().toLowerCase();
  if (!answer) return fallback;
  return ["y", "yes", "是", "好", "可以"].includes(answer);
}

function secret() {
  return crypto.randomBytes(24).toString("hex");
}

async function main() {
  console.log("Mia onboard");
  console.log("This writes .env.local and keeps setup terminal-first.\n");

  const env = {
    OPENAI_BASE_URL: "https://api.openai.com/v1",
    MODEL_NAME: "gpt-4o-mini",
    TRANSCRIPTION_MODEL: "whisper-1",
    AGENT_SERVICE_URL: "http://localhost:8000",
    MIA_INTERNAL_SECRET: secret(),
    SENDBLUE_WEBHOOK_SECRET: "",
    TELEGRAM_WEBHOOK_SECRET: secret(),
    COMPOSIO_ENABLED: "false",
    MIA_WEB_ADMIN_EMAIL: "owner@mia.local",
    MIA_WEB_ADMIN_PASSWORD: "mia-local-admin",
    MIA_WEB_AUTH_SECRET: secret(),
    ...readEnv(path.join(root, ".env.example")),
    ...readEnv(envPath),
  };

  env.OPENAI_API_KEY = await ask("OpenAI-compatible API key", env.OPENAI_API_KEY);
  env.OPENAI_BASE_URL = await ask("OpenAI-compatible base URL", env.OPENAI_BASE_URL);
  env.MODEL_NAME = await ask("Model name", env.MODEL_NAME);
  env.TRANSCRIPTION_MODEL = await ask("Voice transcription model", env.TRANSCRIPTION_MODEL);

  const tunnel = await ask("Public agent URL for webhooks, or leave local", env.AGENT_SERVICE_URL);
  env.AGENT_SERVICE_URL = tunnel;

  if (await yes("Enable iMessage via SendBlue", Boolean(env.SENDBLUE_API_KEY_ID))) {
    env.SENDBLUE_API_KEY_ID = await ask("SendBlue API key id", env.SENDBLUE_API_KEY_ID);
    env.SENDBLUE_API_SECRET_KEY = await ask(
      "SendBlue secret key",
      env.SENDBLUE_API_SECRET_KEY,
    );
    env.SENDBLUE_FROM_NUMBER = await ask("SendBlue from number", env.SENDBLUE_FROM_NUMBER);
    env.OWNER_PHONE_NUMBER = await ask("Owner phone number", env.OWNER_PHONE_NUMBER);
    env.SENDBLUE_WEBHOOK_SECRET = await ask(
      "SendBlue webhook secret",
      env.SENDBLUE_WEBHOOK_SECRET || secret(),
    );
  }

  if (await yes("Enable Telegram bot channel", Boolean(env.TELEGRAM_BOT_TOKEN))) {
    env.TELEGRAM_BOT_TOKEN = await ask("Telegram bot token from @BotFather", env.TELEGRAM_BOT_TOKEN);
    env.TELEGRAM_OWNER_CHAT_ID = await ask(
      "Telegram owner chat id (can fill later after first message)",
      env.TELEGRAM_OWNER_CHAT_ID,
    );
    env.TELEGRAM_ALLOWED_CHAT_IDS = await ask(
      "Allowed Telegram chat ids, comma-separated",
      env.TELEGRAM_ALLOWED_CHAT_IDS || env.TELEGRAM_OWNER_CHAT_ID,
    );
    env.TELEGRAM_WEBHOOK_SECRET = await ask(
      "Telegram webhook secret",
      env.TELEGRAM_WEBHOOK_SECRET || secret(),
    );
  }

  if (await yes("Enable Composio CLI tools", env.COMPOSIO_ENABLED === "true")) {
    env.COMPOSIO_ENABLED = "true";
    console.log("Composio enabled. If not logged in, run: composio login");
  } else {
    env.COMPOSIO_ENABLED = "false";
  }

  writeFileSync(envPath, serializeEnv(env));

  console.log(`\nWrote ${envPath}`);
  console.log("\nNext commands:");
  console.log("  npm run mia:gateway:localtunnel");
  console.log("\nWebhook URLs:");
  const publicAgentUrl = env.AGENT_SERVICE_URL.replace(/\/$/, "");
  console.log(`  SendBlue:  ${publicAgentUrl}/webhooks/sendblue/receive`);
  console.log(`  Telegram:  ${publicAgentUrl}/webhooks/telegram/receive`);
  if (env.TELEGRAM_BOT_TOKEN && env.AGENT_SERVICE_URL.startsWith("https://")) {
    console.log("\nSet Telegram webhook:");
    console.log(
      `  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" -H 'content-type: application/json' -d '{"url":"${publicAgentUrl}/webhooks/telegram/receive","secret_token":"${env.TELEGRAM_WEBHOOK_SECRET}"}'`,
    );
  }
}

try {
  await main();
} finally {
  rl.close();
}
