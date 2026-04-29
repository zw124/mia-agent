import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const memoryTier = v.union(
  v.literal("short_term"),
  v.literal("long_term"),
  v.literal("permanent"),
);

const memorySegment = v.union(
  v.literal("preferences"),
  v.literal("facts"),
  v.literal("tasks"),
  v.literal("relationships"),
  v.literal("projects"),
  v.literal("other"),
);

const memoryStatus = v.union(
  v.literal("active"),
  v.literal("merged"),
  v.literal("deleted"),
  v.literal("manual_review"),
);

export default defineSchema({
  messages: defineTable({
    direction: v.union(v.literal("inbound"), v.literal("outbound")),
    messageHandle: v.string(),
    linkedMessageHandle: v.optional(v.string()),
    content: v.string(),
    fromNumber: v.optional(v.string()),
    toNumber: v.optional(v.string()),
    sendblueNumber: v.optional(v.string()),
    service: v.optional(v.string()),
    mediaUrl: v.optional(v.string()),
    groupId: v.optional(v.string()),
    participants: v.array(v.string()),
    status: v.optional(v.string()),
    raw: v.any(),
    createdAt: v.number(),
  })
    .index("by_message_handle", ["messageHandle"])
    .index("by_created_at", ["createdAt"]),

  webhookEvents: defineTable({
    messageHandle: v.optional(v.string()),
    ignored: v.boolean(),
    raw: v.any(),
    createdAt: v.number(),
  }).index("by_created_at", ["createdAt"]),

  thoughtLogs: defineTable({
    messageHandle: v.optional(v.string()),
    runId: v.optional(v.string()),
    node: v.string(),
    content: v.string(),
    activeAgent: v.optional(v.string()),
    createdAt: v.number(),
  })
    .index("by_created_at", ["createdAt"])
    .index("by_message_handle", ["messageHandle"]),

  agentRuns: defineTable({
    runId: v.string(),
    messageHandle: v.optional(v.string()),
    activeAgent: v.optional(v.string()),
    status: v.union(v.literal("running"), v.literal("completed"), v.literal("failed")),
    startedAt: v.number(),
    completedAt: v.optional(v.number()),
    error: v.optional(v.string()),
  })
    .index("by_run_id", ["runId"])
    .index("by_started_at", ["startedAt"]),

  agentSpawns: defineTable({
    runId: v.string(),
    messageHandle: v.string(),
    parentAgent: v.string(),
    name: v.string(),
    objective: v.string(),
    allowedTools: v.array(v.string()),
    status: v.union(
      v.literal("planned"),
      v.literal("running"),
      v.literal("completed"),
      v.literal("failed"),
      v.literal("blocked"),
    ),
    result: v.optional(v.string()),
    error: v.optional(v.string()),
    createdAt: v.number(),
    updatedAt: v.number(),
  })
    .index("by_run_id", ["runId"])
    .index("by_created_at", ["createdAt"]),

  calendarHolds: defineTable({
    title: v.string(),
    day: v.string(),
    time: v.string(),
    sourceMessageHandle: v.string(),
    status: v.union(v.literal("tentative"), v.literal("confirmed"), v.literal("cancelled")),
    createdAt: v.number(),
    updatedAt: v.number(),
  })
    .index("by_day", ["day"])
    .index("by_created_at", ["createdAt"]),

  pendingActions: defineTable({
    code: v.string(),
    requesterNumber: v.string(),
    messageHandle: v.string(),
    runId: v.optional(v.string()),
    kind: v.string(),
    summary: v.string(),
    payload: v.any(),
    risk: v.union(v.literal("safe"), v.literal("approval_required"), v.literal("manual_only")),
    status: v.union(
      v.literal("pending"),
      v.literal("approved"),
      v.literal("completed"),
      v.literal("failed"),
      v.literal("expired"),
    ),
    createdAt: v.number(),
    expiresAt: v.number(),
    approvedAt: v.optional(v.number()),
    completedAt: v.optional(v.number()),
    result: v.optional(v.string()),
    error: v.optional(v.string()),
  })
    .index("by_code", ["code"])
    .index("by_requester_status", ["requesterNumber", "status"])
    .index("by_created_at", ["createdAt"]),

  memories: defineTable({
    content: v.string(),
    tier: memoryTier,
    segment: memorySegment,
    importanceScore: v.number(),
    decayRate: v.number(),
    status: memoryStatus,
    sourceMessageHandle: v.optional(v.string()),
    mergedInto: v.optional(v.id("memories")),
    createdAt: v.number(),
    updatedAt: v.number(),
    lastAccessedAt: v.optional(v.number()),
  })
    .index("by_status_tier_importance", ["status", "tier", "importanceScore"])
    .index("by_segment", ["segment"])
    .index("by_updated_at", ["updatedAt"]),

  memoryCourtRuns: defineTable({
    runId: v.string(),
    localDate: v.string(),
    status: v.union(v.literal("running"), v.literal("completed"), v.literal("failed")),
    startedAt: v.number(),
    completedAt: v.optional(v.number()),
    error: v.optional(v.string()),
  })
    .index("by_run_id", ["runId"])
    .index("by_local_date", ["localDate"])
    .index("by_started_at", ["startedAt"]),

  memoryCourtDecisions: defineTable({
    runId: v.string(),
    memoryIds: v.array(v.string()),
    action: v.union(
      v.literal("delete"),
      v.literal("merge"),
      v.literal("keep"),
      v.literal("manual_review"),
    ),
    finalContent: v.optional(v.string()),
    reason: v.string(),
    proposal: v.optional(v.any()),
    adversarialRounds: v.array(v.any()),
    createdAt: v.number(),
  })
    .index("by_run_id", ["runId"])
    .index("by_created_at", ["createdAt"]),

  systemHeartbeats: defineTable({
    source: v.string(),
    status: v.union(v.literal("ok"), v.literal("degraded"), v.literal("failed")),
    checks: v.any(),
    repairs: v.array(v.string()),
    createdAt: v.number(),
  }).index("by_created_at", ["createdAt"]),
});
