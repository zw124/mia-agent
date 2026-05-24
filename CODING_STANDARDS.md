# Coding Standards

## General

- Prefer clarity over cleverness.
- Keep functions small and single-purpose.
- Use explicit names for state, side effects, and security-sensitive flows.
- Minimize hidden behavior and magic defaults.

## TypeScript / React

- Prefer strict typing and avoid `any` unless there is a hard boundary.
- Keep server and client concerns separated.
- Treat loading, empty, and error states as first-class UI states.
- Make tool traces and approval states explicit in the UI.

## Python

- Prefer explicit data models and narrow tool interfaces.
- Keep orchestration logic testable.
- Fail closed for permissioned operations.
- Log enough context for debugging without leaking secrets.

## Security-sensitive code

- Validate all external input.
- Do not trust browser, webhook, or tool payloads by default.
- Avoid silent privilege escalation.
- Any approval bypass requires explicit maintainer review.

## Tests

- Add regression tests for bugs.
- Add contract tests for API shape changes.
- Keep fixtures representative but minimal.

## Documentation

- Document user-visible changes.
- Document new environment variables.
- Document operational assumptions for integrations.
