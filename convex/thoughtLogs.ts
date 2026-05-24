import { v } from "convex/values";
import { internalMutation, query } from "./_generated/server";

export const record = internalMutation({
  args: {
    messageHandle: v.optional(v.union(v.string(), v.null())),
    runId: v.optional(v.union(v.string(), v.null())),
    node: v.string(),
    content: v.string(),
    activeAgent: v.optional(v.union(v.string(), v.null())),
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

export const byMessageHandle = query({
  args: { messageHandle: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("thoughtLogs")
      .withIndex("by_message_handle", (q) => q.eq("messageHandle", args.messageHandle))
      .order("asc")
      .collect();
  },
});

