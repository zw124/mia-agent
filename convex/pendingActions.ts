import { v } from "convex/values";
import { internalMutation, internalQuery, query } from "./_generated/server";
import { nullableString, pendingActionRisk } from "./validators";

export const create = internalMutation({
  args: {
    requesterNumber: v.string(),
    messageHandle: v.string(),
    runId: v.optional(nullableString),
    kind: v.string(),
    summary: v.string(),
    payload: v.any(),
    risk: pendingActionRisk,
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    const code = String(Math.floor(100000 + Math.random() * 900000));
    await ctx.db.insert("pendingActions", {
      code,
      requesterNumber: args.requesterNumber,
      messageHandle: args.messageHandle,
      runId: args.runId ?? undefined,
      kind: args.kind,
      summary: args.summary,
      payload: args.payload,
      risk: args.risk,
      status: "pending",
      createdAt: now,
      expiresAt: now + 10 * 60 * 1000,
    });
    return { code };
  },
});

export const findLatestPending = internalQuery({
  args: { requesterNumber: v.string() },
  handler: async (ctx, args) => {
    const actions = await ctx.db
      .query("pendingActions")
      .withIndex("by_requester_status", (q) =>
        q.eq("requesterNumber", args.requesterNumber).eq("status", "pending"),
      )
      .order("desc")
      .take(2);
    const active = actions.filter((action) => action.expiresAt >= Date.now());
    if (active.length !== 1) {
      return null;
    }
    return active[0];
  },
});

export const approveLatest = internalMutation({
  args: { requesterNumber: v.string() },
  handler: async (ctx, args) => {
    const actions = await ctx.db
      .query("pendingActions")
      .withIndex("by_requester_status", (q) =>
        q.eq("requesterNumber", args.requesterNumber).eq("status", "pending"),
      )
      .order("desc")
      .take(2);
    const active = actions.filter((action) => action.expiresAt >= Date.now());
    if (active.length === 0) {
      return { ok: false, reason: "none" };
    }
    if (active.length > 1) {
      return { ok: false, reason: "multiple" };
    }
    const action = active[0];
    await ctx.db.patch(action._id, { status: "approved", approvedAt: Date.now() });
    return { ok: true, action };
  },
});

export const complete = internalMutation({
  args: {
    code: v.string(),
    requesterNumber: v.string(),
    result: v.string(),
  },
  handler: async (ctx, args) => {
    const action = await ctx.db
      .query("pendingActions")
      .withIndex("by_code", (q) => q.eq("code", args.code))
      .first();
    if (action && action.requesterNumber === args.requesterNumber) {
      await ctx.db.patch(action._id, {
        status: "completed",
        completedAt: Date.now(),
        result: args.result,
      });
    }
    return { ok: true };
  },
});

export const fail = internalMutation({
  args: {
    code: v.string(),
    requesterNumber: v.string(),
    error: v.string(),
  },
  handler: async (ctx, args) => {
    const action = await ctx.db
      .query("pendingActions")
      .withIndex("by_code", (q) => q.eq("code", args.code))
      .first();
    if (action && action.requesterNumber === args.requesterNumber) {
      await ctx.db.patch(action._id, {
        status: "failed",
        completedAt: Date.now(),
        error: args.error,
      });
    }
    return { ok: true };
  },
});

export const recent = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("pendingActions")
      .withIndex("by_created_at")
      .order("desc")
      .take(args.limit ?? 20);
  },
});

export const expireStale = internalMutation({
  args: {},
  handler: async (ctx) => {
    const now = Date.now();
    const stale = await ctx.db
      .query("pendingActions")
      .withIndex("by_created_at")
      .filter((q) =>
        q.and(q.eq(q.field("status"), "pending"), q.lt(q.field("expiresAt"), now)),
      )
      .take(100);
    for (const action of stale) {
      await ctx.db.patch(action._id, {
        status: "expired",
        completedAt: now,
        error: "System heartbeat expired this approval.",
      });
    }
    return {
      expired: stale.length,
      codes: stale.map((action) => action.code),
    };
  },
});
