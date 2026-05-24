import { NextResponse } from "next/server";
import { setSession, validateLogin } from "../../../../lib/auth";

export const runtime = "nodejs";

type LoginPayload = {
  email?: string;
  password?: string;
};

export async function POST(request: Request) {
  const body = (await request.json()) as LoginPayload;
  const email = body.email?.trim() ?? "";
  const password = body.password ?? "";
  if (!(await validateLogin(email, password))) {
    return NextResponse.json({ ok: false, error: "Invalid credentials" }, { status: 401 });
  }
  await setSession(email);
  return NextResponse.json({ ok: true, user: { email, role: "owner" } });
}
