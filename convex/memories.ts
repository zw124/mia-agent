import { v } from "convex/values";
import { internalMutation, internalQuery, query } from "./_generated/server";
import { memorySegment } from "./validators";

function tierForImportance(score: number) {
  if (score >= 0.9) return "permanent" as const;
  if (score >= 0.55) return "long_term" as const;
  return "short_term" as const;
}

function decayForImportance(score: number) {
  if (score >= 0.9) return 0;
  if (score >= 0.55) return 0.05;
  return 0.18;
}

export const upsert = internalMutation({
  args: {
    content: v.string(),
    segment: memorySegment,
    sourceMessageHandle: v.string(),
    importanceScore: v.number(),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    await ctx.db.insert("memories", {
      content: args.content,
      tier: tierForImportance(args.importanceScore),
      segment: args.segment,
      importanceScore: Math.max(0, Math.min(1, args.importanceScore)),
      decayRate: decayForImportance(args.importanceScore),
      status: "active",
      sourceMessageHandle: args.sourceMessageHandle,
      createdAt: now,
      updatedAt: now,
    });
    return { ok: true };
  },
});

export const courtCandidates = internalQuery({
  args: {},
  handler: async (ctx) => {
    const active = await ctx.db
      .query("memories")
      .withIndex("by_status_tier_importance", (q) => q.eq("status", "active"))
      .take(200);
    return {
      memories: active.map((memory) => ({
        id: memory._id,
        content: memory.content,
        tier: memory.tier,
        segment: memory.segment,
        importanceScore: memory.importanceScore,
        decayRate: memory.decayRate,
        status: memory.status,
        lastAccessedAt: memory.lastAccessedAt,
      })),
    };
  },
});

export const relevant = internalQuery({
  args: { message: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    const tokens = new Set(
      args.message
        .toLowerCase()
        .split(/[^a-z0-9\u4e00-\u9fff]+/u)
        .filter((token) => token.length >= 2),
    );
    const active = await ctx.db
      .query("memories")
      .withIndex("by_status_tier_importance", (q) => q.eq("status", "active"))
      .take(200);
    const scored = active.map((memory) => {
      const text = `${memory.content} ${memory.segment}`.toLowerCase();
      const lexicalScore = Array.from(tokens).reduce(
        (score, token) => score + (text.includes(token) ? 1 : 0),
        0,
      );
      const tierBoost = memory.tier === "permanent" ? 2 : memory.tier === "long_term" ? 1 : 0;
      return { memory, score: lexicalScore + tierBoost + memory.importanceScore };
    });
    return {
      memories: scored
        .sort((a, b) => b.score - a.score)
        .slice(0, args.limit ?? 8)
        .map(({ memory }) => ({
          id: memory._id,
          content: memory.content,
          tier: memory.tier,
          segment: memory.segment,
          importanceScore: memory.importanceScore,
        })),
    };
  },
});

export const list = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("memories")
      .withIndex("by_updated_at")
      .order("desc")
      .take(args.limit ?? 40);
  },
});
