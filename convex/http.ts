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

function postRoute(path: string, handler: (ctx: any, body: any) => Promise<unknown>) {
  http.route({
    path,
    method: "POST",
    handler: httpAction(async (ctx, request) => {
      if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
      return json(await handler(ctx, await request.json()));
    }),
  });
}

function emptyPostRoute(path: string, handler: (ctx: any) => Promise<unknown>) {
  http.route({
    path,
    method: "POST",
    handler: httpAction(async (ctx, request) => {
      if (!isAuthorized(request)) return json({ error: "unauthorized" }, 401);
      return json(await handler(ctx));
    }),
  });
}

postRoute("/internal/webhook-event", (ctx, body) =>
  ctx.runMutation(internal.messages.recordWebhookEvent, body),
);
postRoute("/internal/inbound-message", (ctx, body) =>
  ctx.runMutation(internal.messages.recordInbound, body),
);
postRoute("/internal/outbound-message", (ctx, body) =>
  ctx.runMutation(internal.messages.recordOutbound, body),
);
postRoute("/internal/thought-log", (ctx, body) =>
  ctx.runMutation(internal.thoughtLogs.record, body),
);
postRoute("/internal/agent-run/start", (ctx, body) =>
  ctx.runMutation(internal.agentRuns.start, body),
);
postRoute("/internal/agent-run/complete", (ctx, body) =>
  ctx.runMutation(internal.agentRuns.complete, body),
);
postRoute("/internal/agent-run/fail", (ctx, body) =>
  ctx.runMutation(internal.agentRuns.fail, body),
);
postRoute("/internal/agent-spawn", (ctx, body) =>
  ctx.runMutation(internal.agentSpawns.record, body),
);
postRoute("/internal/agent-spawn/status", (ctx, body) =>
  ctx.runMutation(internal.agentSpawns.updateStatus, body),
);
postRoute("/internal/memory", (ctx, body) =>
  ctx.runMutation(internal.memories.upsert, body),
);
postRoute("/internal/memories/relevant", (ctx, body) =>
  ctx.runQuery(internal.memories.relevant, body),
);
postRoute("/internal/calendar/holds", (ctx, body) =>
  ctx.runMutation(internal.calendar.createHold, body),
);
postRoute("/internal/calendar/day", (ctx, body) =>
  ctx.runQuery(internal.calendar.listForDay, body),
);
postRoute("/internal/pending-actions/create", (ctx, body) =>
  ctx.runMutation(internal.pendingActions.create, body),
);
postRoute("/internal/pending-actions/approve", (ctx, body) =>
  ctx.runMutation(internal.pendingActions.approveLatest, body),
);
postRoute("/internal/pending-actions/complete", (ctx, body) =>
  ctx.runMutation(internal.pendingActions.complete, body),
);
postRoute("/internal/pending-actions/fail", (ctx, body) =>
  ctx.runMutation(internal.pendingActions.fail, body),
);
emptyPostRoute("/internal/memory-court/candidates", (ctx) =>
  ctx.runQuery(internal.memories.courtCandidates, {}),
);
postRoute("/internal/memory-court/apply", (ctx, body) =>
  ctx.runMutation(internal.memoryCourt.applyDecisions, body),
);

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

postRoute("/internal/heartbeat/record", (ctx, body) =>
  ctx.runMutation(internal.systemHealth.recordHeartbeat, body),
);

export default http;
