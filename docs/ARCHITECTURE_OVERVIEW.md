# Architecture Overview

## Main parts

- `apps/dashboard`: Next.js web application
- `apps/desktop`: Electron desktop shell and packaging
- `apps/agent-service`: Python agent orchestration and tool execution
- `convex`: backend state and event models
- `website`: static or parallel web-facing assets

## Key runtime idea

Mia is not just a chat UI. It combines:

- authenticated user entry points;
- agent orchestration;
- visible tool execution;
- memory/session continuity;
- desktop runtime packaging.

## Important boundaries

- UI should not silently imply capabilities the backend does not perform.
- Security-sensitive operations should pass through explicit approval or audited tool flows.
- Community and commercial licensing boundaries must remain documented and deliberate.
