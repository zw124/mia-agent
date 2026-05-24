# Development

## Prerequisites

- Node.js compatible with the repository toolchain
- npm
- Python and the local virtual environment requirements for `apps/agent-service`
- Optional: Convex CLI, Supabase CLI, Vercel CLI

## Local workflow

Typical development flow:

1. Install dependencies.
2. Configure environment variables from `.env.example`.
3. Start the dashboard and backend services.
4. Run tests before opening a pull request.

## Main commands

```bash
npm install
npm run typecheck
npm run build
npm run desktop:dev
npm run test
```

## Service notes

- The dashboard is a Next.js app.
- The agent service is a Python service under `apps/agent-service`.
- Desktop packaging lives under `apps/desktop`.
- Convex and Supabase files may coexist during migration periods; review architecture docs before changing persistence boundaries.
