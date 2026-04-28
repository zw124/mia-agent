# Mia Personal AI Agent

Mia is a personal iMessage AI agent monorepo. It connects iMessage to a LangGraph-based agent service, Convex realtime storage, and a Next.js operations dashboard.

## What it does

- Receives and sends iMessages via SendBlue
- Routes intent with a parent router and dynamic sub-agents
- Stores messages, runs, and memories in Convex
- Provides a realtime ops dashboard for setup and monitoring

## Requirements

- Node.js 18+
- Python 3.11+
- Convex account
- SendBlue account
- OpenAI-compatible model endpoint

## Quick Start

```bash
npm install
cp .env.example .env
npm run mia:gateway
```

Open the dashboard at:

```text
http://localhost:3000
```

## Configure

Fill in these env vars in `.env`:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `MODEL_NAME`
- `CONVEX_URL`
- `CONVEX_SITE_URL`
- `NEXT_PUBLIC_CONVEX_URL`
- `AGENT_SERVICE_URL`
- `MIA_INTERNAL_SECRET`
- `SENDBLUE_API_KEY_ID`
- `SENDBLUE_API_SECRET_KEY`
- `SENDBLUE_FROM_NUMBER`
- `SENDBLUE_WEBHOOK_SECRET`
- `OWNER_PHONE_NUMBER`

## Useful Commands

```bash
npm run dev
npm run dev:dashboard
npm run dev:convex
```

## License

See LICENSE.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=zhiliao000-star/mia-agent&type=Date)](https://www.star-history.com/#zhiliao000-star/mia-agent&Date)
