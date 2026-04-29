import { v } from "convex/values";
import { internalMutation, query } from "./_generated/server";

const heartbeatStatus = v.union(v.literal("ok"), v.literal("degraded"), v.literal("failed"));

export const recordHeartbeat = internalMutation({
  args: {
    source: v.string(),
    status: heartbeatStatus,
    checks: v.any(),
    repairs: v.array(v.string()),
  },
  handler: async (ctx, args) => {
    const id = await ctx.db.insert("systemHeartbeats", {
      source: args.source,
      status: args.status,
      checks: args.checks,
      repairs: args.repairs,
      createdAt: Date.now(),
    });
    return { ok: true, id };
  },
});

export const recent = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("systemHeartbeats")
      .withIndex("by_created_at")
      .order("desc")
      .take(args.limit ?? 20);
  },
});
