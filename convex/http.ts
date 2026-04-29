import { httpRouter } from "convex/server";
import { internal } from "./_generated/api";
import { httpAction } from "./_generated/server";

const http = httpRouter();

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify({ result: data }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function isAuthorized(request: Request) {
  const expected = process.env.MIA_INTERNAL_SECRET;
  return Boolean(expected) && request.headers.get("x-mia-internal-secret") === expected;
}

http.route({
  path: "/internal/webhook-event",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.messages.recordWebhookEvent, body));
  }),
});

http.route({
  path: "/internal/inbound-message",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.messages.recordInbound, body));
  }),
});

http.route({
  path: "/internal/outbound-message",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.messages.recordOutbound, body));
  }),
});

http.route({
  path: "/internal/thought-log",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.thoughtLogs.record, body));
  }),
});

http.route({
  path: "/internal/agent-run/start",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.agentRuns.start, body));
  }),
});

http.route({
  path: "/internal/agent-run/complete",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.agentRuns.complete, body));
  }),
});

http.route({
  path: "/internal/agent-run/fail",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.agentRuns.fail, body));
  }),
});

http.route({
  path: "/internal/agent-spawn",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.agentSpawns.record, body));
  }),
});

http.route({
  path: "/internal/agent-spawn/status",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.agentSpawns.updateStatus, body));
  }),
});

http.route({
  path: "/internal/memory",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.memories.upsert, body));
  }),
});

http.route({
  path: "/internal/memories/relevant",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runQuery(internal.memories.relevant, body));
  }),
});

http.route({
  path: "/internal/calendar/holds",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.calendar.createHold, body));
  }),
});

http.route({
  path: "/internal/calendar/day",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runQuery(internal.calendar.listForDay, body));
  }),
});

http.route({
  path: "/internal/pending-actions/create",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.pendingActions.create, body));
  }),
});

http.route({
  path: "/internal/pending-actions/approve",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.pendingActions.approveLatest, body));
  }),
});

http.route({
  path: "/internal/pending-actions/complete",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.pendingActions.complete, body));
  }),
});

http.route({
  path: "/internal/pending-actions/fail",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.pendingActions.fail, body));
  }),
});

http.route({
  path: "/internal/memory-court/candidates",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    return json(await ctx.runQuery(internal.memories.courtCandidates, {}));
  }),
});

http.route({
  path: "/internal/memory-court/apply",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.memoryCourt.applyDecisions, body));
  }),
});

http.route({
  path: "/internal/heartbeat/repair",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    const staleRuns = await ctx.runMutation(internal.agentRuns.repairStale, {
      maxAgeMs:
        typeof body.maxRunAgeMs === "number" && Number.isFinite(body.maxRunAgeMs)
          ? body.maxRunAgeMs
          : 15 * 60 * 1000,
    });
    const expiredApprovals = await ctx.runMutation(internal.pendingActions.expireStale, {});
    return json({ staleRuns, expiredApprovals });
  }),
});

http.route({
  path: "/internal/heartbeat/record",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
    const body = await request.json();
    return json(await ctx.runMutation(internal.systemHealth.recordHeartbeat, body));
  }),
});

export default http;
