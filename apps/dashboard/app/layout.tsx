import type { Metadata } from "next";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import "./styles.css";
import { ConvexClientProvider } from "../components/convex-client-provider";

export const metadata: Metadata = {
  title: "Mia | Personal AI agent",
  description: "A local AI agent app for coding, tools, and desktop automation.",
};

function parseEnvValue(name: string) {
  if (process.env[name]) return process.env[name];

  const candidates = [
    path.join(process.cwd(), ".env.local"),
    path.join(process.cwd(), "..", ".env.local"),
    path.join(process.cwd(), "..", "..", ".env.local"),
  ];

  for (const envFile of candidates) {
    if (!existsSync(envFile)) continue;
    const lines = readFileSync(envFile, "utf8").split(/\r?\n/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const separator = trimmed.indexOf("=");
      if (separator < 0) continue;
      if (trimmed.slice(0, separator).trim() !== name) continue;
      return trimmed.slice(separator + 1).trim().replace(/^['"]|['"]$/g, "");
    }
  }

  return "";
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const configuredConvexUrl = parseEnvValue("NEXT_PUBLIC_CONVEX_URL");
  const convexUrl =
    configuredConvexUrl || (process.env.NODE_ENV === "production" ? "" : "http://127.0.0.1:3210");

  return (
    <html lang="en">
      <body>
        <ConvexClientProvider url={convexUrl}>{children}</ConvexClientProvider>
      </body>
    </html>
  );
}
