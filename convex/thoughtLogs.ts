import { v } from "convex/values";
import { internalMutation, query } from "./_generated/server";
import { nullableString } from "./validators";

export const record = internalMutation({
  args: {
    messageHandle: v.optional(nullableString),
    runId: v.optional(nullableString),
    node: v.string(),
    content: v.string(),
    activeAgent: v.optional(nullableString),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("thoughtLogs", {
      messageHandle: args.messageHandle ?? undefined,
      runId: args.runId ?? undefined,
      node: args.node,
      content: args.content,
      activeAgent: args.activeAgent ?? undefined,
      createdAt: Date.now(),
    });
    return { ok: true };
  },
});

export const recent = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("thoughtLogs")
      .withIndex("by_created_at")
      .order("desc")
      .take(args.limit ?? 40);
  },
});

export const activeAgent = query({
  args: {},
  handler: async (ctx) => {
    const recent = await ctx.db.query("thoughtLogs").withIndex("by_created_at").order("desc").take(1);
    return recent[0]?.activeAgent ?? null;
  },
});
