import { NextResponse } from "next/server";
import { currentUser, hasRegisteredUsers } from "../../../../lib/auth";

export const runtime = "nodejs";

export async function GET() {
  const user = await currentUser();
  return NextResponse.json({ authenticated: Boolean(user), user, hasRegisteredUsers: hasRegisteredUsers() });
}
