import { v } from "convex/values";
import { internalMutation, query } from "./_generated/server";
import { nullableBoolean, nullableNumber, nullableString } from "./validators";

const inboundPayload = v.object({
  accountEmail: v.optional(nullableString),
  content: v.string(),
  is_outbound: v.boolean(),
  status: v.optional(nullableString),
  error_code: v.optional(nullableNumber),
  error_message: v.optional(nullableString),
  error_reason: v.optional(nullableString),
  message_handle: v.string(),
  date_sent: v.optional(nullableString),
  date_updated: v.optional(nullableString),
  from_number: v.optional(nullableString),
  number: v.string(),
  to_number: v.optional(nullableString),
  was_downgraded: v.optional(nullableBoolean),
  plan: v.optional(nullableString),
  media_url: v.optional(nullableString),
  message_type: v.optional(nullableString),
  group_id: v.optional(nullableString),
  participants: v.array(v.string()),
  send_style: v.optional(nullableString),
  opted_out: v.optional(nullableBoolean),
  error_detail: v.optional(nullableString),
  sendblue_number: v.optional(nullableString),
  service: v.optional(nullableString),
  group_display_name: v.optional(nullableString),
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
  args: { payload: inboundPayload },
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
      raw: args.payload,
      createdAt: Date.now(),
    });
    return { accepted: true };
  },
});

export const recordOutbound = internalMutation({
  args: {
    inboundMessageHandle: v.string(),
    toNumber: v.string(),
    content: v.string(),
    sendblueResponse: v.any(),
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
      raw: args.sendblueResponse,
      createdAt: Date.now(),
    });
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
