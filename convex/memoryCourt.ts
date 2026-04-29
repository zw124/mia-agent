import { v } from "convex/values";
import type { Id } from "./_generated/dataModel";
import { internal } from "./_generated/api";
import { internalAction, internalMutation, internalQuery, query } from "./_generated/server";
import { courtDecisionAction, nullableString } from "./validators";

function sameMemoryIds(left: unknown, right: string[]) {
  return Array.isArray(left) && left.join(",") === right.join(",");
}

function proposalMatchesDecision(proposal: unknown, memoryIds: string[]) {
  if (!proposal || typeof proposal !== "object" || !("memory_ids" in proposal)) {
    return false;
  }
  return sameMemoryIds(proposal.memory_ids, memoryIds);
}

function newYorkLocalParts(now: Date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const byType = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    localDate: `${byType.year}-${byType.month}-${byType.day}`,
    hour: Number(byType.hour),
    minute: Number(byType.minute),
  };
}

export const maybeRunNightlyCourt = internalAction({
  args: {},
  handler: async (ctx) => {
    const { localDate, hour } = newYorkLocalParts(new Date());
    if (hour !== 3) {
      return { skipped: true, reason: "not_3am_new_york", localDate };
    }

    const existing = await ctx.runQuery(internal.memoryCourt.findRunByLocalDate, { localDate });
    if (existing) {
      return { skipped: true, reason: "already_ran", localDate };
    }

    const runId = crypto.randomUUID();
    await ctx.runMutation(internal.memoryCourt.startRun, { runId, localDate });

    const agentServiceUrl = process.env.AGENT_SERVICE_URL;
    const secret = process.env.MIA_INTERNAL_SECRET;
    if (!agentServiceUrl || !secret) {
      await ctx.runMutation(internal.memoryCourt.failRun, {
        runId,
        error: "Missing AGENT_SERVICE_URL or MIA_INTERNAL_SECRET",
      });
      return { skipped: false, runId, error: "missing_env" };
    }

    try {
      const response = await fetch(`${agentServiceUrl.replace(/\/$/, "")}/internal/memory-court/run`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-mia-internal-secret": secret,
        },
        body: JSON.stringify({ runId, localDate }),
      });
      if (!response.ok) {
        throw new Error(`Agent service returned ${response.status}: ${await response.text()}`);
      }
      await ctx.runMutation(internal.memoryCourt.completeRun, { runId });
      return { skipped: false, runId, localDate };
    } catch (error) {
      await ctx.runMutation(internal.memoryCourt.failRun, {
        runId,
        error: error instanceof Error ? error.message : String(error),
      });
      return { skipped: false, runId, error: String(error) };
    }
  },
});

export const findRunByLocalDate = internalQuery({
  args: { localDate: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("memoryCourtRuns")
      .withIndex("by_local_date", (q) => q.eq("localDate", args.localDate))
      .first();
  },
});

export const startRun = internalMutation({
  args: { runId: v.string(), localDate: v.string() },
  handler: async (ctx, args) => {
    await ctx.db.insert("memoryCourtRuns", {
      runId: args.runId,
      localDate: args.localDate,
      status: "running",
      startedAt: Date.now(),
    });
    return { ok: true };
  },
});

export const completeRun = internalMutation({
  args: { runId: v.string() },
  handler: async (ctx, args) => {
    const run = await ctx.db
      .query("memoryCourtRuns")
      .withIndex("by_run_id", (q) => q.eq("runId", args.runId))
      .unique();
    if (run) {
      await ctx.db.patch(run._id, { status: "completed", completedAt: Date.now() });
    }
    return { ok: true };
  },
});

export const failRun = internalMutation({
  args: { runId: v.string(), error: v.string() },
  handler: async (ctx, args) => {
    const run = await ctx.db
      .query("memoryCourtRuns")
      .withIndex("by_run_id", (q) => q.eq("runId", args.runId))
      .unique();
    if (run) {
      await ctx.db.patch(run._id, { status: "failed", completedAt: Date.now(), error: args.error });
    }
    return { ok: true };
  },
});

export const applyDecisions = internalMutation({
  args: {
    runId: v.string(),
    proposals: v.array(v.any()),
    adversarialRounds: v.array(v.any()),
    judgeDecisions: v.array(
      v.object({
        memory_ids: v.array(v.string()),
        action: courtDecisionAction,
        final_content: v.optional(nullableString),
        reason: v.string(),
      }),
    ),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    for (const decision of args.judgeDecisions) {
      await ctx.db.insert("memoryCourtDecisions", {
        runId: args.runId,
        memoryIds: decision.memory_ids,
        action: decision.action,
        finalContent: decision.final_content ?? undefined,
        reason: decision.reason,
        proposal: args.proposals.find((proposal) =>
          proposalMatchesDecision(proposal, decision.memory_ids),
        ),
        adversarialRounds: args.adversarialRounds.filter((round) =>
          proposalMatchesDecision(
            args.proposals[round?.proposal_index ?? -1],
            decision.memory_ids,
          ),
        ),
        createdAt: now,
      });

      for (const memoryId of decision.memory_ids) {
        const memory = await ctx.db.get(memoryId as Id<"memories">);
        if (!memory || memory.tier === "permanent") {
          continue;
        }
        if (decision.action === "delete") {
          await ctx.db.patch(memory._id, { status: "deleted", updatedAt: now });
        }
        if (decision.action === "manual_review") {
          await ctx.db.patch(memory._id, { status: "manual_review", updatedAt: now });
        }
      }

      if (decision.action === "merge" && decision.final_content) {
        const mergedId = await ctx.db.insert("memories", {
          content: decision.final_content,
          tier: "long_term",
          segment: "other",
          importanceScore: 0.7,
          decayRate: 0.04,
          status: "active",
          createdAt: now,
          updatedAt: now,
        });
        for (const memoryId of decision.memory_ids) {
          const memory = await ctx.db.get(memoryId as Id<"memories">);
          if (memory && memory.tier !== "permanent") {
            await ctx.db.patch(memory._id, {
              status: "merged",
              mergedInto: mergedId,
              updatedAt: now,
            });
          }
        }
      }
    }
    return { ok: true };
  },
});

export const recentRuns = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("memoryCourtRuns")
      .withIndex("by_started_at")
      .order("desc")
      .take(args.limit ?? 10);
  },
});

export const recentDecisions = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("memoryCourtDecisions")
      .withIndex("by_created_at")
      .order("desc")
      .take(args.limit ?? 20);
  },
});
