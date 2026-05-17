# Mia Personal AI Agent

Mia is a local-first personal AI agent controlled from iMessage, a web console, and a desktop companion. The current build focuses on a simple owner workflow: start the gateway, point SendBlue at the public agent URL, then talk to Mia from iMessage.

## Current Capabilities

- Terminal-first onboarding with `npm run mia:onboard` or `mia-agent onboard`.
- iMessage control through SendBlue inbound and outbound webhooks.
- Telegram bot channel with webhook, owner allowlist, and shared approval flow.
- Fast intent routing that chooses between direct reply, memory update, tool task, coding orchestra, and design orchestra.
- AI-selected orchestration depth: Mia decides `brief`, `standard`, or `deep` based on task risk and complexity instead of always running a full loop.
- Visible iMessage progress updates for longer tasks, so the user sees what Mia is doing instead of only a typing indicator.
- Voice-message handling through SendBlue audio `media_url` plus OpenAI-compatible transcription.
- DuckDuckGo web search fallback, with optional SearXNG if `SEARXNG_BASE_URL` is set.
- Flexible Composio CLI tools for connected apps: auth check, link, search, schema, dry-run, execute, and scripted workflows after approval.
- Computer-use tools for observation, safe planning, approval previews, screenshots, keyboard/mouse actions, app opening, shell-safe workspace status, text-to-speech, and owner-approved outbound iMessage.
- OpenClaw-style `user.md` profile loaded into agent prompts for stable owner preferences.
- Open CoDesign-style `DESIGN.md` design-system baton loaded into design tasks.
- Coding orchestra for software engineering, debugging, review, architecture, and agent-design work.
- Design orchestra for UI, UX, product pages, dashboards, setup flows, chat interfaces, and visual-system work.
- Convex-backed messages, runs, thought logs, agent spawns, memories, pending approvals, system health, and memory court.
- Web dashboard scaffold for login, setup, status, and chat shell.
- Desktop companion scaffold for macOS, Windows, and Linux.

## Quick Start

Install dependencies:

```bash
npm install
```

Run terminal onboarding:

```bash
npm run mia:onboard
```

Python package path:

```bash
cd apps/agent-service
pipx install .
mia-agent onboard
mia-agent serve
```

After PyPI publishing:

```bash
pipx install mia-agent-service
mia-agent onboard
mia-agent serve
```

For development without `pipx`:

```bash
cd apps/agent-service
pip install -e .
mia-agent doctor --env ../../.env.local
mia-agent serve --env ../../.env.local
```

Or create env manually:

```bash
cp .env.example .env.local
```

Start the full local gateway with a LocalTunnel public URL for SendBlue:

```bash
npm run mia:gateway:localtunnel
```

The gateway manages:

- Dashboard: `http://localhost:3000`
- Agent service: `http://localhost:8000/health`
- Convex dev service
- Optional public tunnel for SendBlue webhooks

If you only want dashboard plus Convex:

```bash
npm run dev
```

## SendBlue iMessage Setup

Set these in `.env.local`:

```bash
SENDBLUE_API_KEY_ID=
SENDBLUE_API_SECRET_KEY=
SENDBLUE_FROM_NUMBER=
OWNER_PHONE_NUMBER=
```

Set the SendBlue inbound webhook URL to:

```text
https://YOUR_PUBLIC_AGENT_URL/webhooks/sendblue/receive
```

For localtunnel, `YOUR_PUBLIC_AGENT_URL` is the URL printed by:

```bash
npm run mia:gateway:localtunnel
```

If you set `SENDBLUE_WEBHOOK_SECRET`, configure the same signing secret in SendBlue.

## Telegram Setup

Create a Telegram bot with `@BotFather`, then run:

```bash
npm run mia:onboard
```

Choose Telegram and paste the bot token. The onboarder writes:

```bash
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_OWNER_CHAT_ID=
TELEGRAM_ALLOWED_CHAT_IDS=
```

Telegram inbound webhook:

```text
https://YOUR_PUBLIC_AGENT_URL/webhooks/telegram/receive
```

Set the webhook:

```bash
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H 'content-type: application/json' \
  -d '{"url":"https://YOUR_PUBLIC_AGENT_URL/webhooks/telegram/receive","secret_token":"YOUR_TELEGRAM_WEBHOOK_SECRET"}'
```

Access policy is fail-closed when `TELEGRAM_ALLOWED_CHAT_IDS` or `TELEGRAM_OWNER_CHAT_ID` is set. Approvals from Telegram use the same `approve` command as iMessage.

To find your Telegram chat ID, DM your bot once and inspect the gateway logs or Telegram `getUpdates`:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
```

## Environment Variables

Core model:

```bash
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
TRANSCRIPTION_MODEL=whisper-1
```

Convex and service URLs:

```bash
CONVEX_URL=
CONVEX_SITE_URL=
NEXT_PUBLIC_CONVEX_URL=
AGENT_SERVICE_URL=http://localhost:8000
MIA_INTERNAL_SECRET=change-me
```

SendBlue:

```bash
SENDBLUE_API_KEY_ID=
SENDBLUE_API_SECRET_KEY=
SENDBLUE_FROM_NUMBER=
SENDBLUE_WEBHOOK_SECRET=
SENDBLUE_STATUS_CALLBACK=
OWNER_PHONE_NUMBER=
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_OWNER_CHAT_ID=
TELEGRAM_ALLOWED_CHAT_IDS=
```

Search:

```bash
SEARXNG_BASE_URL=
COMPOSIO_ENABLED=false
```

If `SEARXNG_BASE_URL` is empty, Mia uses DuckDuckGo HTML search fallback.

Web login:

```bash
MIA_WEB_ADMIN_EMAIL=owner@mia.local
MIA_WEB_ADMIN_PASSWORD=mia-local-admin
MIA_WEB_AUTH_SECRET=change-this-before-deploy
```

Change the web login values before deployment.

## Agent Routing

Mia starts every message with a parent router. The router chooses one mode:

- `fast_reply`: simple direct answer.
- `memory_update`: store a durable preference, fact, task, relationship, or project detail.
- `tool_task`: bounded tool use for search, computer actions, calendar, workspace status, or outbound iMessage.
- `coding_orchestra`: bounded specialist flow for programming and agent work.
- `design_orchestra`: bounded specialist flow for product/UI/design work.

For orchestra tasks, the router also chooses:

- `brief`: smallest specialist path.
- `standard`: useful quality without slow full review.
- `deep`: full specialist pass for high-stakes, ambiguous, broad, or production-grade requests.

This avoids the old problem where every task ran a full loop even when the user asked a simple question.

## Progress And Voice

For longer iMessage tasks, Mia can send short progress messages before the final answer. This makes the agent feel active instead of only showing the native typing indicator.

Voice flow:

1. User sends an audio iMessage.
2. SendBlue includes an audio `media_url` in the webhook.
3. Mia downloads the media and calls the OpenAI-compatible transcription endpoint.
4. Mia replies with the recognized text and then handles it like a normal message.

Voice requires:

```bash
OPENAI_API_KEY=
OPENAI_BASE_URL=
TRANSCRIPTION_MODEL=whisper-1
```

## Memory And Design Context

`user.md` is the stable owner profile. Use it for durable preferences that should shape all replies.

`DESIGN.md` is the design-system baton. Use it for stable UI/design choices such as typography, colors, spacing, component states, and do/don't rules.

These files are read by the agent service and injected into relevant prompts. They are intentionally plain Markdown so they can be edited by hand.

## Computer Use

Computer-use tools are staged for safety:

- Observe first with screenshot/app context.
- Plan before action for non-trivial UI control.
- Preview risk before clicks, typing, app control, shell, or outbound iMessage.
- Require owner-only access for sensitive local operations.
- Use pending approval for actions that should not execute silently.

Useful owner commands over iMessage:

```text
approve
auto approve
stop auto approve
```

The same `approve` command works from Telegram when the sender is the configured `TELEGRAM_OWNER_CHAT_ID`.

## Composio

Mia includes a flexible Composio tool surface:

- `composio_search`: search for tool slugs by natural language.
- `composio_whoami`: check CLI login status.
- `composio_link`: connect a toolkit account such as Gmail, GitHub, Slack, or Google Calendar.
- `composio_schema`: inspect the required payload for a tool slug.
- `composio_dry_run`: validate a payload without performing the action.
- `composio_execute`: request approval, then execute a tool slug with JSON payload.
- `composio_run`: request approval, then run an inline Composio JavaScript workflow for multi-tool tasks.

Enable it during onboarding or set:

```bash
COMPOSIO_ENABLED=true
```

Then authenticate Composio in the same shell/user environment:

```bash
composio login
```

Expected agent flow:

```text
composio_whoami -> composio_search -> composio_link if needed -> composio_schema -> composio_dry_run -> composio_execute
```

For multi-step connected-app work, Mia can use `composio_run` after approval. Execution is approval-gated because Composio tools can touch external accounts such as Gmail, GitHub, Slack, calendars, and CRMs.

## Useful Commands

```bash
npm run mia:gateway
npm run mia:onboard
npm run mia:gateway:localtunnel
npm run mia:gateway:ngrok
npm run dev
npm run dev:dashboard
npm run dev:convex
npm run desktop:dev
npm run desktop:package
npm run typecheck
npm run test:python
npm test
```

Python package commands:

```bash
mia-agent onboard
mia-agent doctor
mia-agent serve --host 127.0.0.1 --port 8000
```

Python-only checks:

```bash
cd apps/agent-service
pytest -q
ruff check .
```

From the repo root with the local venv:

```bash
/Users/zw00/Desktop/mia-agent/.venv/bin/pytest -q apps/agent-service
/Users/zw00/Desktop/mia-agent/.venv/bin/ruff check apps/agent-service
```

## Deployment Shape

Deploy `apps/dashboard` as the web control center. The deployed web app owns login, status, setup, and dashboard UI. The desktop companion logs into the same web console and starts the local gateway for computer control. SendBlue points inbound iMessage webhooks at the public agent service URL.

For production:

- Use HTTPS for `AGENT_SERVICE_URL`, `CONVEX_SITE_URL`, and webhook URLs.
- Use strong `MIA_INTERNAL_SECRET` and `MIA_WEB_AUTH_SECRET`.
- Rotate exposed SendBlue/OpenAI credentials.
- Keep `OWNER_PHONE_NUMBER` set so sensitive tools are owner-gated.

## PyPI Release

The Python package lives in `apps/agent-service` and publishes the `mia-agent` CLI.

Package name:

```text
mia-agent-service
```

Local build check:

```bash
cd apps/agent-service
python -m pip install build
python -m build
```

GitHub Actions workflow:

```text
.github/workflows/publish-pypi.yml
```

Recommended publishing path is PyPI Trusted Publishing, not a long-lived API token. Configure PyPI once with:

```text
Owner/repository: zw124/mia-agent
Workflow name: publish-pypi.yml
Environment name: pypi
Package name: mia-agent-service
```

Then publish by creating a GitHub Release or manually running the workflow.

## Project Layout

```text
apps/agent-service   FastAPI agent service, router, tools, orchestras
apps/dashboard       Next.js web console
apps/desktop         Electron desktop companion scaffold
convex               Convex schema, HTTP actions, messages, memory, logs
scripts              Gateway and launch-agent scripts
user.md              Owner profile
DESIGN.md            Design-system baton
```

## License

See `LICENSE`.
