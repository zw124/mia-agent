import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const create = mutation({
  args: { title: v.optional(v.string()) },
  handler: async (ctx, args) => {
    const now = Date.now();
    return await ctx.db.insert("sessions", {
      title: args.title ?? "New Chat",
      createdAt: now,
      updatedAt: now,
    });
  },
});

export const list = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("sessions")
      .withIndex("by_updated_at")
      .order("desc")
      .collect();
  },
});

export const get = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.sessionId);
  },
});

export const updateTitle = mutation({
  args: { sessionId: v.id("sessions"), title: v.string() },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.sessionId, {
      title: args.title,
      updatedAt: Date.now(),
    });
  },
});

export const touch = mutation({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.sessionId, {
      updatedAt: Date.now(),
    });
  },
});
