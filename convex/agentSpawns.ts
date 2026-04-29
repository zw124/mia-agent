import { v } from "convex/values";
import { internalMutation, query } from "./_generated/server";
import { agentSpawnStatus, nullableString } from "./validators";

export const record = internalMutation({
  args: {
    runId: v.string(),
    messageHandle: v.string(),
    parentAgent: v.string(),
    name: v.string(),
    objective: v.string(),
    allowedTools: v.array(v.string()),
    status: v.optional(agentSpawnStatus),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    await ctx.db.insert("agentSpawns", {
      runId: args.runId,
      messageHandle: args.messageHandle,
      parentAgent: args.parentAgent,
      name: args.name,
      objective: args.objective,
      allowedTools: args.allowedTools,
      status: args.status ?? "planned",
      createdAt: now,
      updatedAt: now,
    });
    return { ok: true };
  },
});

export const updateStatus = internalMutation({
  args: {
    runId: v.string(),
    name: v.string(),
    status: agentSpawnStatus,
    result: v.optional(nullableString),
    error: v.optional(nullableString),
  },
  handler: async (ctx, args) => {
    const spawn = await ctx.db
      .query("agentSpawns")
      .withIndex("by_run_id", (q) => q.eq("runId", args.runId))
      .filter((q) => q.eq(q.field("name"), args.name))
      .order("desc")
      .first();
    if (!spawn) {
      return { ok: false, reason: "not_found" };
    }
    await ctx.db.patch(spawn._id, {
      status: args.status,
      result: args.result ?? undefined,
      error: args.error ?? undefined,
      updatedAt: Date.now(),
    });
    return { ok: true };
  },
});

export const recent = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("agentSpawns")
      .withIndex("by_created_at")
      .order("desc")
      .take(args.limit ?? 30);
  },
});
