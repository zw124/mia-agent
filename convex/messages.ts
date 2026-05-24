import { v } from "convex/values";
import { internalMutation, internalQuery, query } from "./_generated/server";

const inboundPayload = v.object({
  accountEmail: v.optional(v.union(v.string(), v.null())),
  content: v.string(),
  is_outbound: v.boolean(),
  status: v.optional(v.union(v.string(), v.null())),
  error_code: v.optional(v.union(v.number(), v.null())),
  error_message: v.optional(v.union(v.string(), v.null())),
  error_reason: v.optional(v.union(v.string(), v.null())),
  message_handle: v.string(),
  date_sent: v.optional(v.union(v.string(), v.null())),
  date_updated: v.optional(v.union(v.string(), v.null())),
  from_number: v.optional(v.union(v.string(), v.null())),
  number: v.string(),
  to_number: v.optional(v.union(v.string(), v.null())),
  was_downgraded: v.optional(v.union(v.boolean(), v.null())),
  plan: v.optional(v.union(v.string(), v.null())),
  media_url: v.optional(v.union(v.string(), v.null())),
  message_type: v.optional(v.union(v.string(), v.null())),
  group_id: v.optional(v.union(v.string(), v.null())),
  participants: v.array(v.string()),
  send_style: v.optional(v.union(v.string(), v.null())),
  opted_out: v.optional(v.union(v.boolean(), v.null())),
  error_detail: v.optional(v.union(v.string(), v.null())),
  sendblue_number: v.optional(v.union(v.string(), v.null())),
  service: v.optional(v.union(v.string(), v.null())),
  group_display_name: v.optional(v.union(v.string(), v.null())),
});

export const recordWebhookEvent = internalMutation({
  args: { payload: v.any(), ignored: v.boolean() },
  handler: async (ctx, args) => {
    await ctx.db.insert("webhookEvents", {
      messageHandle: args.payload?.message_handle,
      ignored: args.ignored,
      raw: args.payload,
      createdAt: Date.now(),
    });
    return { ok: true };
  },
});

export const recordInbound = internalMutation({
  args: { payload: inboundPayload, sessionId: v.optional(v.id("sessions")) },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("messages")
      .withIndex("by_message_handle", (q) => q.eq("messageHandle", args.payload.message_handle))
      .unique();
    if (existing) {
      return { accepted: false };
    }

    await ctx.db.insert("webhookEvents", {
      messageHandle: args.payload.message_handle,
      ignored: false,
      raw: args.payload,
      createdAt: Date.now(),
    });
    await ctx.db.insert("messages", {
      direction: "inbound",
      messageHandle: args.payload.message_handle,
      content: args.payload.content,
      fromNumber: args.payload.from_number ?? args.payload.number,
      toNumber: args.payload.to_number ?? undefined,
      sendblueNumber: args.payload.sendblue_number ?? undefined,
      service: args.payload.service ?? undefined,
      mediaUrl: args.payload.media_url ?? undefined,
      groupId: args.payload.group_id ?? undefined,
      participants: args.payload.participants,
      status: args.payload.status ?? undefined,
      sessionId: args.sessionId,
      raw: args.payload,
      createdAt: Date.now(),
    });
    if (args.sessionId) {
      await ctx.db.patch(args.sessionId, {
        updatedAt: Date.now(),
      });
    }
    return { accepted: true };
  },
});

export const recordOutbound = internalMutation({
  args: {
    inboundMessageHandle: v.string(),
    toNumber: v.string(),
    content: v.string(),
    sendblueResponse: v.any(),
    sessionId: v.optional(v.id("sessions")),
  },
  handler: async (ctx, args) => {
    const messageHandle =
      typeof args.sendblueResponse?.message_handle === "string"
        ? args.sendblueResponse.message_handle
        : `local-${crypto.randomUUID()}`;
    await ctx.db.insert("messages", {
      direction: "outbound",
      messageHandle,
      linkedMessageHandle: args.inboundMessageHandle,
      content: args.content,
      toNumber: args.toNumber,
      participants: [args.toNumber],
      status: args.sendblueResponse?.status,
      sessionId: args.sessionId,
      raw: args.sendblueResponse,
      createdAt: Date.now(),
    });
    if (args.sessionId) {
      await ctx.db.patch(args.sessionId, {
        updatedAt: Date.now(),
      });
    }
    return { ok: true };
  },
});

export const recent = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_created_at")
      .order("desc")
      .take(args.limit ?? 20);
  },
});

export const recentInternal = internalQuery({
  args: {
    limit: v.optional(v.number()),
    participant: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const limit = Math.min(Math.max(args.limit ?? 12, 1), 40);
    const rows = await ctx.db
      .query("messages")
      .withIndex("by_created_at")
      .order("desc")
      .take(limit * 3);

    const participant = args.participant;
    const filtered = participant
      ? rows.filter((message) => {
          return (
            message.fromNumber === participant ||
            message.toNumber === participant ||
            message.participants.includes(participant)
          );
        })
      : rows;

    return filtered.slice(0, limit).map((message) => ({
      direction: message.direction,
      content: message.content,
      fromNumber: message.fromNumber,
      toNumber: message.toNumber,
      messageHandle: message.messageHandle,
      linkedMessageHandle: message.linkedMessageHandle,
      createdAt: message.createdAt,
    }));
  },
});

export const recentWebhookEvents = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("webhookEvents")
      .withIndex("by_created_at")
      .order("desc")
      .take(args.limit ?? 20);
  },
});

export const bySession = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("messages")
      .withIndex("by_session_id", (q) => q.eq("sessionId", args.sessionId))
      .order("asc")
      .collect();
  },
});
