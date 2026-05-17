import { NextResponse } from "next/server";
import { registerUser, setSession } from "../../../../lib/auth";

export const runtime = "nodejs";

type RegisterPayload = {
  email?: string;
  password?: string;
};

export async function POST(request: Request) {
  const body = (await request.json()) as RegisterPayload;
  const result = registerUser(body.email ?? "", body.password ?? "");
  if (!result.ok || !result.email) {
    return NextResponse.json(result, { status: 400 });
  }
  await setSession(result.email);
  return NextResponse.json({ ok: true, user: { email: result.email, role: "owner" } });
}
