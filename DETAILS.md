# Mia Agent Detailed Technical Guide

This file documents the Mia project in detail. README.md is the short public entry point; this document explains how the system is wired, what each module owns, how data moves, and where to modify behavior.

## 1. What Mia Is

Mia is a personal AI agent system that uses iMessage as the user interface.

The project is a monorepo with three major runtime pieces:

- A Python FastAPI service that receives SendBlue webhooks, runs LangGraph workflows, calls an OpenAI-compatible model, executes approved tools, and sends replies.
- A Convex TypeScript backend that stores messages, thought logs, agent runs, spawned agents, memory, pending approvals, and memory-court audit records.
- A Next.js dashboard that provides onboarding, setup, realtime observability, and operational views.

The goal is not to build a simple chatbot. Mia is structured as local personal infrastructure: a parent router decides what kind of task the user sent, creates temporary sub-agent specs when tools are needed, injects only the approved tools into that sub-agent node, records the entire process in Convex, and returns a concise iMessage reply.

## 2. Repository Layout

```text
.
├── README.md
├── DETAILS.md
├── index.html
├── site.css
├── assets/
│   └── mia-logo.png
├── apps/
│   ├── agent-service/
│   │   └── mia/
│   │       ├── main.py
│   │       ├── settings.py
│   │       ├── llm.py
│   │       ├── models.py
│   │       ├── graphs/
│   │       │   ├── router.py
│   │       │   └── memory_court.py
│   │       ├── integrations/
│   │       │   ├── convex.py
│   │       │   └── sendblue.py
│   │       └── tools/
│   │           ├── registry.py
│   │           ├── calendar.py
│   │           ├── coding.py
│   │           ├── computer.py
│   │           └── search.py
│   └── dashboard/
│       ├── app/
│       │   ├── api/setup/
│       │   ├── layout.tsx
│       │   ├── page.tsx
│       │   └── styles.css
│       ├── components/
│       │   ├── convex-client-provider.tsx
│       │   └── mia-dashboard.tsx
│       └── public/
│           └── mia-logo.png
├── convex/
│   ├── schema.ts
│   ├── http.ts
│   ├── messages.ts
│   ├── thoughtLogs.ts
│   ├── agentRuns.ts
│   ├── agentSpawns.ts
│   ├── memories.ts
│   ├── pendingActions.ts
│   ├── memoryCourt.ts
│   ├── calendar.ts
│   └── crons.ts
└── scripts/
    ├── mia-gateway.mjs
    └── install-mia-gateway-launch-agent.mjs
```

## 3. Runtime Architecture

The normal iMessage path is:

```text
User iMessage
  -> SendBlue inbound webhook
  -> FastAPI POST /webhooks/sendblue/receive
  -> Convex stores inbound message and webhook event
  -> LangGraph parent router classifies the task
  -> direct reply, memory update, or dynamic sub-agent
  -> response composer creates final iMessage text
  -> SendBlue outbound message API
  -> Convex stores outbound message and run status
  -> Dashboard updates live through Convex useQuery
```

The nightly memory cleanup path is:

```text
Convex cron
  -> checks America/New_York local 3 AM window
  -> ensures only one run per local date
  -> calls FastAPI POST /internal/memory-court/run
  -> Python LangGraph Memory Court runs Consolidator, Adversarial Agent, Judge
  -> decisions are posted back to Convex
  -> Convex updates memories and writes court audit records
  -> Dashboard updates live
```

## 4. Environment Variables

Mia is intentionally provider-flexible. The LLM is configured only through OpenAI-compatible variables.

### Required for LLM

```text
OPENAI_API_KEY
OPENAI_BASE_URL
MODEL_NAME
```

The Python service reads these in `apps/agent-service/mia/settings.py`. The LLM wrapper validates them before use. No Anthropic SDK is used.

### Required for Convex

```text
CONVEX_URL
CONVEX_SITE_URL
NEXT_PUBLIC_CONVEX_URL
MIA_INTERNAL_SECRET
```

- `CONVEX_URL` is used by the dashboard client.
- `NEXT_PUBLIC_CONVEX_URL` is required by the Next.js browser bundle.
- `CONVEX_SITE_URL` is used by Python to call Convex HTTP actions.
- `MIA_INTERNAL_SECRET` protects internal Python-to-Convex and Convex-to-Python calls.

### Required for SendBlue

```text
SENDBLUE_API_KEY_ID
SENDBLUE_API_SECRET_KEY
SENDBLUE_FROM_NUMBER
SENDBLUE_WEBHOOK_SECRET
SENDBLUE_STATUS_CALLBACK
```

- The inbound webhook must point to `/webhooks/sendblue/receive`.
- The SendBlue webhook secret is checked against the incoming `sb-signing-secret` header.
- Outbound replies use SendBlue's `POST /api/send-message` endpoint.

### Owner and Tools

```text
OWNER_PHONE_NUMBER
SEARXNG_BASE_URL
AGENT_SERVICE_URL
```

- `OWNER_PHONE_NUMBER` gates owner-only tools such as file access and terminal commands.
- `SEARXNG_BASE_URL` enables the `web_search` tool.
- `AGENT_SERVICE_URL` is used by setup flows and Convex actions when the agent service needs to be called by URL.

## 5. FastAPI Service

The FastAPI app lives in:

```text
apps/agent-service/mia/main.py
```

### `GET /health`

Returns basic readiness:

```json
{
  "status": "ok",
  "llm": "configured"
}
```

`llm` becomes `configured` only when all three LLM variables exist.

### `POST /webhooks/sendblue/receive`

This is the SendBlue inbound webhook endpoint.

Responsibilities:

- Validate `sb-signing-secret` against `SENDBLUE_WEBHOOK_SECRET`.
- Ignore outbound events so Mia does not reply to its own messages.
- Record webhook and inbound message data in Convex.
- Dedupe by `message_handle`.
- Support iMessage approval by accepting the literal message `approve`.
- Start an `agentRuns` row.
- Fetch relevant memories from Convex.
- Run the LangGraph router graph.
- Send the final reply through SendBlue.
- Record the outbound reply in Convex.
- Mark the run completed or failed.

### Approval Message Path

If the inbound message content is exactly `approve` after trimming and lowercasing:

- Mia checks that the sender is `OWNER_PHONE_NUMBER`.
- Convex finds the latest pending action for that owner number.
- The Python service executes the pending action locally.
- Convex marks it completed or failed.
- SendBlue sends a completion reply.

This keeps approval inside iMessage. The user does not need to paste approval codes into a terminal.

### `POST /internal/memory-court/run`

This endpoint is called by Convex cron/action code.

It requires:

```text
x-mia-internal-secret: MIA_INTERNAL_SECRET
```

It expects:

```json
{
  "runId": "...",
  "localDate": "YYYY-MM-DD"
}
```

It loads candidate memories from Convex, runs the Memory Court LangGraph workflow, and posts decisions back to Convex.

## 6. SendBlue Integration

The SendBlue client is in:

```text
apps/agent-service/mia/integrations/sendblue.py
```

Outbound messages are sent with:

```text
POST https://api.sendblue.co/api/send-message
```

Headers:

```text
Content-Type: application/json
sb-api-key-id: SENDBLUE_API_KEY_ID
sb-api-secret-key: SENDBLUE_API_SECRET_KEY
```

Body:

```json
{
  "content": "reply text",
  "from_number": "SENDBLUE_FROM_NUMBER",
  "number": "recipient number",
  "status_callback": "optional callback URL"
}
```

Inbound payloads are normalized by the `SendBlueWebhook` model in `apps/agent-service/mia/models.py`.

Important inbound fields:

- `content`
- `message_handle`
- `from_number`
- `to_number`
- `sendblue_number`
- `service`
- `media_url`
- `group_id`
- `participants`

## 7. Convex Integration

The Python-to-Convex client lives in:

```text
apps/agent-service/mia/integrations/convex.py
```

It posts to Convex HTTP routes under `CONVEX_SITE_URL`.

Every internal request includes:

```text
x-mia-internal-secret: MIA_INTERNAL_SECRET
```

Convex routes are defined in:

```text
convex/http.ts
```

The internal route surface includes:

- `/internal/webhook-event`
- `/internal/inbound-message`
- `/internal/outbound-message`
- `/internal/thought-log`
- `/internal/agent-run/start`
- `/internal/agent-run/complete`
- `/internal/agent-run/fail`
- `/internal/agent-spawn`
- `/internal/agent-spawn/status`
- `/internal/memory`
- `/internal/memories/relevant`
- `/internal/calendar/holds`
- `/internal/calendar/day`
- `/internal/pending-actions/create`
- `/internal/pending-actions/approve`
- `/internal/pending-actions/complete`
- `/internal/pending-actions/fail`
- `/internal/memory-court/candidates`
- `/internal/memory-court/apply`

## 8. Convex Schema

The schema lives in:

```text
convex/schema.ts
```

### `messages`

Stores inbound and outbound iMessage records.

Fields:

- `direction`: `inbound` or `outbound`
- `messageHandle`
- `linkedMessageHandle`
- `content`
- `fromNumber`
- `toNumber`
- `sendblueNumber`
- `service`
- `mediaUrl`
- `groupId`
- `participants`
- `status`
- `raw`
- `createdAt`

Indexes:

- `by_message_handle`
- `by_created_at`

### `webhookEvents`

Stores raw webhook receipts and whether they were ignored.

Fields:

- `messageHandle`
- `ignored`
- `raw`
- `createdAt`

### `thoughtLogs`

Stores internal agent trace lines for the dashboard.

Fields:

- `messageHandle`
- `runId`
- `node`
- `content`
- `activeAgent`
- `createdAt`

### `agentRuns`

Stores a full router/run lifecycle.

Fields:

- `runId`
- `messageHandle`
- `activeAgent`
- `status`: `running`, `completed`, or `failed`
- `startedAt`
- `completedAt`
- `error`

### `agentSpawns`

Stores dynamic sub-agents created by the parent router.

Fields:

- `runId`
- `messageHandle`
- `parentAgent`
- `name`
- `objective`
- `allowedTools`
- `status`: `planned`, `running`, `completed`, `failed`, or `blocked`
- `result`
- `error`
- `createdAt`
- `updatedAt`

This table is what the dashboard uses to show realtime generated agents and their assigned tools.

### `calendarHolds`

Stores simple local calendar holds.

Fields:

- `title`
- `day`
- `time`
- `sourceMessageHandle`
- `status`: `tentative`, `confirmed`, or `cancelled`
- `createdAt`
- `updatedAt`

### `pendingActions`

Stores approval-required local actions.

Fields:

- `code`
- `requesterNumber`
- `messageHandle`
- `runId`
- `kind`
- `summary`
- `payload`
- `risk`: `safe`, `approval_required`, or `manual_only`
- `status`: `pending`, `approved`, `completed`, `failed`, or `expired`
- `createdAt`
- `expiresAt`
- `approvedAt`
- `completedAt`
- `result`
- `error`

The iMessage `approve` flow uses this table.

### `memories`

Stores Mia's three-tier memory system.

Fields:

- `content`
- `tier`: `short_term`, `long_term`, or `permanent`
- `segment`: `preferences`, `facts`, `tasks`, `relationships`, `projects`, or `other`
- `importanceScore`
- `decayRate`
- `status`: `active`, `merged`, `deleted`, or `manual_review`
- `sourceMessageHandle`
- `mergedInto`
- `createdAt`
- `updatedAt`
- `lastAccessedAt`

Indexes:

- `by_status_tier_importance`
- `by_segment`
- `by_updated_at`

### `memoryCourtRuns`

Stores each nightly court run.

Fields:

- `runId`
- `localDate`
- `status`
- `startedAt`
- `completedAt`
- `error`

### `memoryCourtDecisions`

Stores final court decisions and the debate context.

Fields:

- `runId`
- `memoryIds`
- `action`: `delete`, `merge`, `keep`, or `manual_review`
- `finalContent`
- `reason`
- `proposal`
- `adversarialRounds`
- `createdAt`

## 9. Parent Router and Dynamic Sub-Agents

The router graph lives in:

```text
apps/agent-service/mia/graphs/router.py
```

### Router State

The LangGraph state includes:

- `run_id`
- `message`
- `relevant_memories`
- `from_number`
- `sendblue_number`
- `message_handle`
- `route`
- `sub_agent_name`
- `sub_agent_objective`
- `allowed_tools`
- `agent_result`
- `reply`
- `thoughts`

### Valid Routes

The parent router can return only:

- `direct_reply`
- `dynamic_sub_agent`
- `memory_update`

The parent router is intentionally not allowed to call tools. It only classifies and, when needed, creates a sub-agent specification.

### Router Output

The parent router must return strict JSON:

```json
{
  "route": "dynamic_sub_agent",
  "reason": "why this route was selected",
  "sub_agent_name": "browser_worker",
  "sub_agent_objective": "open Wikipedia in the browser",
  "allowed_tools": ["open_url"]
}
```

If the model returns invalid JSON, the system attempts a repair pass with a separate router repair prompt. If repair still fails, it falls back to `direct_reply` with no tool authorization.

### Dynamic Sub-Agent Execution

When route is `dynamic_sub_agent`:

1. The router records a planned row in `agentSpawns`.
2. The dynamic node checks whether requested tools exist.
3. Owner-only tools are rejected unless the sender matches `OWNER_PHONE_NUMBER`.
4. The tool registry is constructed for this message/run.
5. Only `allowed_tools` are injected into the sub-agent.
6. The LLM is bound to those tools with `.bind_tools(tools)`.
7. If the sub-agent does not call a tool, the run is marked blocked rather than pretending success.
8. Executed tools are logged in `thoughtLogs`.
9. The sub-agent result returns to the composer.

This is the key behavior: the parent creates the sub-agent, but the sub-agent gets only the tools assigned to that specific node.

## 10. Tools

Tool registration lives in:

```text
apps/agent-service/mia/tools/registry.py
```

Available tool names:

- `list_calendar_events`
- `create_calendar_hold`
- `explain_code_request`
- `propose_test_cases`
- `update_plan`
- `session_status`
- `agents_list`
- `tools_inventory`
- `exec`
- `process`
- `read`
- `write`
- `edit`
- `apply_patch`
- `open_url`
- `open_app`
- `get_frontmost_app`
- `list_running_apps`
- `screenshot_desktop`
- `read_file`
- `list_directory`
- `file_info`
- `search_files`
- `write_file`
- `delete_file`
- `append_file`
- `replace_in_file`
- `create_directory`
- `copy_file`
- `move_file`
- `run_terminal_command`
- `process_start`
- `process_list`
- `process_read`
- `process_kill`
- `sessions_list`
- `sessions_history`
- `sessions_spawn`
- `sessions_send`
- `sessions_yield`
- `subagents`
- `gateway`
- `nodes`
- `canvas`
- `image_generate`
- `music_generate`
- `video_generate`
- `send_imessage`
- `message`
- `create_reminder`
- `cron`
- `click_screen`
- `type_text`
- `press_key`
- `scroll`
- `fetch_webpage`
- `web_fetch`
- `get_clipboard`
- `set_clipboard`
- `show_notification`
- `speak_text`
- `tts`
- `image_info`
- `image`
- `extract_pdf_text`
- `pdf`
- `web_search`

Owner-only tools:

- `open_url`
- `open_app`
- `get_frontmost_app`
- `list_running_apps`
- `screenshot_desktop`
- `read_file`
- `list_directory`
- `file_info`
- `search_files`
- `write_file`
- `delete_file`
- `append_file`
- `replace_in_file`
- `create_directory`
- `copy_file`
- `move_file`
- `run_terminal_command`
- `process_start`
- `process_list`
- `process_read`
- `process_kill`
- `click_screen`
- `type_text`
- `press_key`
- `scroll`
- `get_clipboard`
- `set_clipboard`
- `show_notification`
- `speak_text`
- `image_info`
- `extract_pdf_text`

### OpenClaw-Style Computer Layer

The root `openclaw/` repository was used as the design reference for expanding Mia's host-control surface. Mia does not embed OpenClaw's full TypeScript runtime inside the Python LangGraph service. Instead, Mia exposes the same kind of practical control surface through native Python tools that fit Mia's router, approval, and Convex audit architecture.

The expanded computer layer now covers:

- Browser and URL opening through `open_url`.
- Active application inspection through `get_frontmost_app`.
- Running application inspection through `list_running_apps`.
- Desktop capture through `screenshot_desktop`, saved under `.mia/screenshots`.
- Local text reading through `read_file`.
- Directory listing through `list_directory`.
- File metadata through `file_info`.
- Local file path search through `search_files`.
- Webpage fetching through `fetch_webpage`.
- Terminal execution requests through `run_terminal_command`.
- Managed background processes through `process_start`, `process_list`, `process_read`, and `process_kill`.
- OpenClaw-compatible session surfaces through `sessions_list`, `sessions_history`, `sessions_spawn`, `sessions_send`, and `sessions_yield`.
- OpenClaw-compatible orchestration/status surfaces through `subagents`, `gateway`, `nodes`, and `canvas`.
- OpenClaw-compatible exact-name aliases through `exec`, `process`, `read`, `write`, `edit`, and `apply_patch`.
- Provider-gated generation surfaces through `image_generate`, `music_generate`, and `video_generate`.
- Outbound iMessage requests through `send_imessage`.
- OpenClaw-compatible `message` alias for outbound iMessage.
- macOS reminder creation through `create_reminder`.
- OpenClaw-compatible `cron` alias backed by macOS Reminders.
- File mutation requests through `write_file`, `append_file`, `replace_in_file`, `delete_file`, `create_directory`, `copy_file`, and `move_file`.
- UI control requests through `click_screen`, `type_text`, `press_key`, and `scroll`.
- Clipboard inspection and mutation through `get_clipboard` and `set_clipboard`.
- Local notifications through `show_notification`.
- macOS speech output through `speak_text`.
- OpenClaw-compatible `tts` alias.
- Image metadata inspection through `image_info`.
- OpenClaw-compatible `image` alias.
- PDF text extraction through `extract_pdf_text`.
- OpenClaw-compatible `pdf` alias.
- OpenClaw-compatible web fetch naming through `web_fetch`.

Actions that can mutate local state or interact with the active UI are routed through `pendingActions`. The user approves them from iMessage by replying `approve`. This keeps Mia powerful while preserving a clear audit trail in Convex.

The approval language is intentionally natural:

- Mia asks `Do you approve?` with the action summary.
- The owner can reply `approve`, `yes`, `ok`, `do it`, `批准`, `同意`, or `可以`.
- The owner can reply `auto approve` to enable auto approval for low-risk UI actions.
- The owner can reply `stop auto approve` or `关闭自动批准` to turn it off.
- Auto approval does not bypass hard-confirm actions such as terminal commands, background process management, SendBlue outbound messages, reminders, or file mutations.
- macOS system permission prompts cannot be approved through iMessage. If macOS blocks screen control, notifications, reminders, or automation, the Mac must be granted permission once in System Settings.

## System Heartbeat

Mia Gateway runs a model-free system heartbeat by default. It does not call the LLM.

Default interval:

```text
120000 ms
```

The interval is clamped to one to five minutes. You can change it with:

```bash
node scripts/mia-gateway.mjs --heartbeat-ms=60000
```

Disable it with:

```bash
node scripts/mia-gateway.mjs --no-heartbeat
```

The heartbeat checks:

- FastAPI `/health`
- Dashboard port
- Gateway process state
- ngrok/OpenClaw-style gateway process state when `--tunnel=ngrok` is active
- Convex internal heartbeat route
- stale `agentRuns`
- expired `pendingActions`

Automatic repairs:

- Restarts the FastAPI agent service if its health check fails and the gateway owns that process.
- Restarts the dashboard if its port closes and the gateway owns that process.
- Restarts ngrok if ngrok mode is active and its local status port closes.
- Restarts Convex dev if Convex internal heartbeat calls fail and the gateway owns Convex.
- Marks running agent runs older than 15 minutes as failed.
- Marks pending approvals past `expiresAt` as expired.
- Writes local heartbeat state to `.mia/heartbeat.json`.
- Records heartbeat snapshots in Convex `systemHeartbeats` when Convex is reachable.

### Calendar Tools

Calendar tools use Convex as the store. They create and list simple local holds, not a full external Google or Apple Calendar integration yet.

### Coding Tools

Coding tools help break down programming requests and propose test cases. They are safe, local, and do not mutate the filesystem by themselves.

### Computer Tools

Computer tools are the bridge to local Mac actions.

The important distinction:

- Safe actions may execute directly.
- Risky actions create `pendingActions`.
- The user can approve through iMessage by sending `approve`.

This design allows Mia to receive a request through iMessage, create a sub-agent, select a computer tool, and use the pending-action system when the action needs explicit owner approval.

### Search Tool

`web_search` uses SearXNG through `SEARXNG_BASE_URL`. The system does not depend on a proprietary search provider.

## 11. Response Composer

The composer is the final node in the router graph.

It receives:

- Original user message
- Relevant memory context
- Agent or sub-agent result

It returns a concise iMessage-friendly reply and logs `compose_reply` to Convex.

The composer is also instructed not to expose internal routing details.

## 12. Memory System

Mia uses three memory tiers:

- `short_term`: temporary context that can decay quickly.
- `long_term`: stable but still reviewable information.
- `permanent`: protected memories that the court must not delete.

Memory classification stores:

- content
- segment
- importance score
- decay rate
- source message handle
- timestamps
- status

When a user sends a durable preference or fact, the router can select `memory_update`. The memory node extracts one durable memory, assigns a segment, assigns an importance score, and upserts it through Convex.

Relevant memories are fetched before each agent run and included in router, sub-agent, and composer prompts.

## 13. Memory Court

The Memory Court graph lives in:

```text
apps/agent-service/mia/graphs/memory_court.py
```

It has three nodes:

- `consolidator`
- `adversarial_agent`
- `judge`

### Consolidator

The consolidator receives candidate memories and proposes:

- delete
- merge
- keep
- manual_review

Candidate filtering excludes permanent memories from deletion consideration and focuses on low importance or high decay memories:

```text
tier != permanent
importanceScore < 0.35 OR decayRate > 0.25
```

If the LLM fails to return valid JSON, deterministic fallback proposals are created.

### Adversarial Agent

The adversarial agent argues against the consolidator.

It runs two rounds before the judge is called.

Each argument includes:

- `proposal_index`
- `argument`
- `should_keep`

### Judge

The judge receives:

- original memories
- consolidator proposals
- two adversarial rounds

It returns final decisions:

- `memory_ids`
- `action`
- `final_content`
- `reason`

Permanent memories must only be kept or moved to manual review.

### Audit Trail

Court decisions are stored in `memoryCourtDecisions` with:

- final decision
- proposal
- adversarial rounds
- reason
- run ID
- timestamp

This makes memory cleanup inspectable instead of silent.

## 14. Convex Cron

Convex cron is responsible for starting nightly cleanup.

The intended semantics are:

- Check America/New_York local time.
- Trigger around 3:00 AM local time.
- Ensure one run per local date.
- Call Python `/internal/memory-court/run`.

This avoids timezone mistakes around daylight saving changes and prevents duplicate court runs.

## 15. Dashboard

The dashboard is in:

```text
apps/dashboard
```

The main component is:

```text
apps/dashboard/components/mia-dashboard.tsx
```

It has two surfaces:

- Onboarding flow
- Realtime operational dashboard

### Onboarding

The onboarding flow is black, minimal, and step-based.

Steps:

1. Welcome
2. Terms
3. GitHub repository
4. Intelligence
5. Convex
6. iMessage
7. Gateway
8. Search
9. Environment

The terms step requires scrolling to the end and checking agreement.

The GitHub step now only requires opening the repository link before continuing. It does not verify whether the repository was actually starred.

The environment step can save configuration locally through:

- `apps/dashboard/app/api/setup/status/route.ts`
- `apps/dashboard/app/api/setup/apply/route.ts`
- `apps/dashboard/app/api/setup/install-dependencies/route.ts`

### Dashboard Sections

The dashboard has these navigation sections:

- Dashboard
- Agents
- Memory
- Automations
- Events
- Consolidation
- Connectors

It uses Convex `useQuery` subscriptions so changes appear live.

Important realtime sources:

- `thoughtLogs.recent`
- `agentRuns.active`
- `agentRuns.recent`
- `agentSpawns.recent`
- `messages.recent`
- `messages.recentWebhookEvents`
- `memories.list`
- `pendingActions.recent`
- `memoryCourt.recentRuns`
- `memoryCourt.recentDecisions`

## 16. Mia Gateway

The gateway script lives in:

```text
scripts/mia-gateway.mjs
```

Run:

```bash
npm run mia:gateway
```

It starts:

- Convex dev
- Next.js dashboard
- FastAPI agent service

Optional ngrok mode:

```bash
npm run mia:gateway:ngrok
```

Useful direct options:

```bash
node scripts/mia-gateway.mjs --help
node scripts/mia-gateway.mjs --no-convex
node scripts/mia-gateway.mjs --no-dashboard
node scripts/mia-gateway.mjs --no-agent
node scripts/mia-gateway.mjs --tunnel=ngrok
node scripts/mia-gateway.mjs --dashboard-port=3000 --agent-port=8000
node scripts/mia-gateway.mjs --verbose
```

Gateway behavior:

- Prints a clean ASCII MIA AGENT banner.
- Writes child process logs to `.mia/logs`.
- Avoids starting duplicate dashboard or agent service processes if the port is already listening.
- Uses `.venv/bin/uvicorn` if present.
- Falls back to `uvicorn` on PATH.

## 17. Public Static Site

The root project website is:

```text
index.html
site.css
assets/mia-logo.png
```

It is intentionally static and minimal so it can be deployed anywhere:

- GitHub Pages
- Vercel static deployment
- Netlify
- Cloudflare Pages
- Any basic file host

Preview locally:

```bash
npm run site:preview
```

Then open:

```text
http://localhost:4173
```

## 18. Local Development Commands

Install dependencies:

```bash
npm install
```

Run all normal services through gateway:

```bash
npm run mia:gateway
```

Run dashboard and Convex only:

```bash
npm run dev
```

Run dashboard only:

```bash
npm run dev:dashboard
```

Run Convex only:

```bash
npm run dev:convex
```

Run typecheck:

```bash
npm run typecheck
```

Run Python tests:

```bash
npm run test:python
```

Run all configured tests:

```bash
npm run test
```

## 19. Public URL for SendBlue

SendBlue must be able to reach the FastAPI service from the public internet.

Local FastAPI endpoint:

```text
http://localhost:8000/webhooks/sendblue/receive
```

Public tunnel endpoint example:

```text
https://your-tunnel.example.com/webhooks/sendblue/receive
```

The SendBlue inbound webhook should be configured with:

- URL: public tunnel URL plus `/webhooks/sendblue/receive`
- Secret: `SENDBLUE_WEBHOOK_SECRET`

If the tunnel changes, update SendBlue's webhook URL.

## 20. Security Model

Mia uses several layers of protection:

- SendBlue webhook secret validates inbound webhook source.
- Convex internal HTTP routes require `MIA_INTERNAL_SECRET`.
- Memory Court endpoint requires `MIA_INTERNAL_SECRET`.
- Owner-only tools require `OWNER_PHONE_NUMBER`.
- Risky local actions can be placed into `pendingActions`.
- Approval is accepted only from the owner number.
- Permanent memories are protected from automatic deletion.

Important operational advice:

- Do not commit real `.env` files.
- Rotate any key pasted into screenshots, chats, logs, or public repositories.
- Do not expose the FastAPI service without the SendBlue secret.
- Do not expose Convex internal routes without `MIA_INTERNAL_SECRET`.
- Keep terminal and file tools owner-gated.

## 21. Common Problems

### iMessage sends but no reply

Check:

- FastAPI service is running on port 8000.
- Public tunnel is online.
- SendBlue webhook URL ends with `/webhooks/sendblue/receive`.
- SendBlue secret matches `SENDBLUE_WEBHOOK_SECRET`.
- Convex env has `MIA_INTERNAL_SECRET`.
- Python env has `CONVEX_SITE_URL`.
- `.mia/logs/agent.log` has no traceback.

### Dashboard says Convex is missing

Check:

- `NEXT_PUBLIC_CONVEX_URL` exists in dashboard env.
- Convex dev has generated `_generated/api`.
- `npx convex dev` is running or the cloud deployment is configured.

### `uvicorn: command not found`

Use the gateway after setting up the Python environment, or install the Python dependencies inside the project virtualenv.

The gateway tries:

```text
.venv/bin/uvicorn
```

then:

```text
uvicorn
```

### SendBlue webhook works but tool actions do not happen

Check:

- The parent router chose `dynamic_sub_agent`.
- `agentSpawns` shows allowed tools.
- Sender matches `OWNER_PHONE_NUMBER` for owner-only tools.
- Approval-required action exists in `pendingActions`.
- Send `approve` from the owner phone number.

### Mia says it opened a URL but nothing opened

The dynamic sub-agent must actually call `open_url`.

Current router logic marks a tool-enabled sub-agent as blocked if no assigned tool call happens. Check:

- `thoughtLogs`
- `agentSpawns.status`
- `.mia/logs/agent.log`

### Memory Court did not run

Check:

- Convex cron is deployed/running.
- It is around the America/New_York 3 AM window.
- There is no existing run for the same local date.
- FastAPI internal endpoint is reachable by Convex.
- `MIA_INTERNAL_SECRET` matches on both sides.

## 22. How to Extend Mia

### Add a New Tool

1. Create a tool in `apps/agent-service/mia/tools/`.
2. Add it to `AVAILABLE_TOOL_NAMES`.
3. Add it to `tool_registry`.
4. Add a description to `public_tool_descriptions`.
5. If risky, add it to `OWNER_ONLY_TOOLS`.
6. If it needs approval, create a pending action instead of executing immediately.
7. Confirm it appears in dashboard `agentSpawns.allowedTools`.

### Add a New Router Route

1. Extend `RouteName`.
2. Add the new route to `VALID_ROUTES`.
3. Update router prompt JSON schema.
4. Add a LangGraph node.
5. Add conditional edge mapping.
6. Ensure the response composer receives `agent_result`.

### Add a New Dashboard Section

1. Add a new `Section` union member.
2. Add it to `navItems`.
3. Add Convex query if needed.
4. Render the section in `DashboardApp`.
5. Keep the style minimal and operational.

### Add a New Memory Segment

1. Update `memorySegment` in `convex/schema.ts`.
2. Update memory extraction prompt.
3. Update dashboard filters if applicable.
4. Run Convex generation/typecheck.

## 23. Current Functional Surface

Implemented now:

- SendBlue inbound webhook endpoint.
- SendBlue outbound reply client.
- OpenAI-compatible LLM configuration.
- LangGraph parent router.
- JSON repair for bad router outputs.
- Direct reply node.
- Memory update node.
- Dynamic sub-agent node.
- Node-local tool injection.
- Tool-call enforcement.
- Owner-only tool gating.
- iMessage approval by sending `approve`.
- Natural approval phrases and owner-only `auto approve`.
- OpenClaw-style desktop inspection tools.
- OpenClaw-style screen control request tools.
- OpenClaw-style local file inspection and mutation request tools.
- OpenClaw-style terminal execution request tool.
- OpenClaw-style process, message, reminder, clipboard, notification, speech, image, PDF, and session-status tools.
- Webpage fetch tool.
- Convex message storage.
- Convex webhook event storage.
- Convex thought logs.
- Convex agent runs.
- Convex dynamic agent spawn records.
- Convex pending actions.
- Convex three-tier memory schema.
- Convex memory court runs and decisions.
- Memory Court LangGraph with two adversarial rounds and judge fallback.
- Realtime Next.js dashboard.
- Full onboarding flow.
- Local setup API routes.
- Gateway process manager.
- Optional ngrok gateway mode.
- Static public project website.

## 24. Mental Model

Think of Mia as four layers:

```text
Interface layer:
  iMessage through SendBlue

Reasoning layer:
  FastAPI + LangGraph + OpenAI-compatible model

State layer:
  Convex messages, runs, thoughts, memories, approvals, court records

Control layer:
  Dashboard, gateway, local tools, approvals
```

The parent router should stay small and strict. It decides, but does not act.

Sub-agents act, but only with the tools explicitly injected into their node.

Convex stores the truth.

The dashboard shows what happened.

The gateway makes local operation tolerable.
