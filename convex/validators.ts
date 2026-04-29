import { v } from "convex/values";

export const agentRunStatus = v.union(
  v.literal("running"),
  v.literal("completed"),
  v.literal("failed"),
);

export const agentSpawnStatus = v.union(
  v.literal("planned"),
  v.literal("running"),
  v.literal("completed"),
  v.literal("failed"),
  v.literal("blocked"),
);

export const calendarHoldStatus = v.union(
  v.literal("tentative"),
  v.literal("confirmed"),
  v.literal("cancelled"),
);

export const courtDecisionAction = v.union(
  v.literal("delete"),
  v.literal("merge"),
  v.literal("keep"),
  v.literal("manual_review"),
);

export const heartbeatStatus = v.union(
  v.literal("ok"),
  v.literal("degraded"),
  v.literal("failed"),
);

export const memorySegment = v.union(
  v.literal("preferences"),
  v.literal("facts"),
  v.literal("tasks"),
  v.literal("relationships"),
  v.literal("projects"),
  v.literal("other"),
);

export const memoryStatus = v.union(
  v.literal("active"),
  v.literal("merged"),
  v.literal("deleted"),
  v.literal("manual_review"),
);

export const memoryTier = v.union(
  v.literal("short_term"),
  v.literal("long_term"),
  v.literal("permanent"),
);

export const pendingActionRisk = v.union(
  v.literal("safe"),
  v.literal("approval_required"),
  v.literal("manual_only"),
);

export const pendingActionStatus = v.union(
  v.literal("pending"),
  v.literal("approved"),
  v.literal("completed"),
  v.literal("failed"),
  v.literal("expired"),
);

export const nullableBoolean = v.union(v.boolean(), v.null());
export const nullableNumber = v.union(v.number(), v.null());
export const nullableString = v.union(v.string(), v.null());
