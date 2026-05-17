import { NextResponse } from "next/server";
import { currentUser } from "../../../lib/auth";

export const runtime = "nodejs";

type ChatPayload = {
  message?: string;
};

export async function POST(request: Request) {
  const user = await currentUser();
  if (!user) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as ChatPayload;
  const message = body.message?.trim();
  if (!message) {
    return NextResponse.json({ ok: false, error: "Missing message" }, { status: 400 });
  }

  const agentUrl = process.env.AGENT_SERVICE_URL || "";
  if (!agentUrl) {
    return NextResponse.json({
      ok: true,
      reply: "Mia is ready in the web app. Finish setup to connect the local agent service.",
      source: "web",
    });
  }

  return NextResponse.json({
    ok: true,
    reply: "I received your message. The web chat shell is connected; the next step is wiring this endpoint to the local agent runtime.",
    source: "web",
  });
}
