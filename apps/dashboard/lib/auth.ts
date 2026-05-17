import { createHmac, timingSafeEqual } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { cookies } from "next/headers";

const COOKIE_NAME = "mia_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30;
const usersFile = path.join(process.cwd(), ".mia", "users.json");

type UserRecord = {
  email: string;
  password: string;
  createdAt: number;
};

function secret() {
  return process.env.MIA_WEB_AUTH_SECRET || process.env.MIA_INTERNAL_SECRET || "dev-secret";
}

function sign(value: string) {
  return createHmac("sha256", secret()).update(value).digest("base64url");
}

function verifySignature(value: string, signature: string) {
  const expected = sign(value);
  const left = Buffer.from(signature);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function createSessionToken(email: string) {
  const payload = Buffer.from(
    JSON.stringify({ email, issuedAt: Date.now(), role: "owner" }),
  ).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

export function readSessionToken(token?: string) {
  if (!token) return null;
  const [payload, signature] = token.split(".");
  if (!payload || !signature || !verifySignature(payload, signature)) return null;
  try {
    return JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as {
      email: string;
      issuedAt: number;
      role: "owner";
    };
  } catch {
    return null;
  }
}

export async function currentUser() {
  const store = await cookies();
  return readSessionToken(store.get(COOKIE_NAME)?.value);
}

export async function setSession(email: string) {
  const store = await cookies();
  store.set(COOKIE_NAME, createSessionToken(email), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: MAX_AGE_SECONDS,
    path: "/",
  });
}

export async function clearSession() {
  const store = await cookies();
  store.delete(COOKIE_NAME);
}

function readUsers(): UserRecord[] {
  if (!existsSync(usersFile)) return [];
  try {
    return JSON.parse(readFileSync(usersFile, "utf8")) as UserRecord[];
  } catch {
    return [];
  }
}

function writeUsers(users: UserRecord[]) {
  mkdirSync(path.dirname(usersFile), { recursive: true });
  writeFileSync(usersFile, JSON.stringify(users, null, 2));
}

export function hasRegisteredUsers() {
  return readUsers().length > 0;
}

export function registerUser(email: string, password: string) {
  const normalizedEmail = email.trim().toLowerCase();
  if (!normalizedEmail || password.length < 6) {
    return { ok: false, error: "Use an email and a password with at least 6 characters." };
  }
  const users = readUsers();
  if (users.some((user) => user.email === normalizedEmail)) {
    return { ok: false, error: "This email is already registered." };
  }
  users.push({ email: normalizedEmail, password, createdAt: Date.now() });
  writeUsers(users);
  return { ok: true, email: normalizedEmail };
}

export function validateLogin(email: string, password: string) {
  const normalizedEmail = email.trim().toLowerCase();
  const users = readUsers();
  if (users.length > 0) {
    return users.some((user) => user.email === normalizedEmail && user.password === password);
  }
  const expectedEmail = process.env.MIA_WEB_ADMIN_EMAIL || "owner@mia.local";
  const expectedPassword = process.env.MIA_WEB_ADMIN_PASSWORD || "mia-local-admin";
  return normalizedEmail === expectedEmail.toLowerCase() && password === expectedPassword;
}
