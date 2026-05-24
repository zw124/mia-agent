import { NextResponse } from "next/server";
import { currentUser } from "../../../lib/auth";

export const runtime = "nodejs";

type ChatPayload = {
  message?: string;
  clientMessageHandle?: string;
  sessionId?: string;
};

function uniqueUrls(urls: string[]) {
  return [...new Set(urls.map((url) => url.replace(/\/$/, "")))];
}

function candidateAgentUrls() {
  const configured = (process.env.AGENT_SERVICE_URL || "http://localhost:8000").trim();
  const local = ["http://127.0.0.1:8000", "http://localhost:8000"];

  if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(configured)) {
    return uniqueUrls([configured, ...local]);
  }

  return uniqueUrls([configured, ...local]);
}

export async function POST(request: Request) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as ChatPayload;
  const message = body.message?.trim();
  const clientMessageHandle = body.clientMessageHandle?.trim();
  const sessionId = body.sessionId?.trim();
  if (!message) {
    return NextResponse.json({ ok: false, error: "Missing message" }, { status: 400 });
  }

  const agentUrls = candidateAgentUrls();
  let lastError = "Could not connect to the local agent service.";

  for (const agentUrl of agentUrls) {
    try {
      const res = await fetch(`${agentUrl}/web/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, client_message_handle: clientMessageHandle, session_id: sessionId }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        const normalized = errorText.toLowerCase();
        const shouldFallback =
          res.status === 502 ||
          res.status === 503 ||
          res.status === 504 ||
          normalized.includes("tunnel unavailable") ||
          normalized.includes("loca.lt");

        lastError = normalized.includes("tunnel unavailable")
          ? "Public tunnel is unavailable. Mia will keep using the local agent when it is running."
          : `Agent service error: ${errorText}`;

        if (shouldFallback) {
          continue;
        }

        return NextResponse.json({ ok: false, error: lastError }, { status: res.status });
      }

      const data = await res.json();
      return NextResponse.json({
        ok: true,
        reply: data.reply,
        route: data.route,
        messageHandle: data.message_handle,
        runId: data.run_id,
        source: "agent",
        agentUrl,
      });
    } catch {
      lastError = `Could not connect to the agent service at ${agentUrl}.`;
    }
  }

  return NextResponse.json({ ok: false, error: lastError }, { status: 503 });
}
