# Testing

## Required checks

Before merging, contributors should run:

```bash
npm run typecheck
npm run build
npm run test
```

## UI changes

For user-facing UI changes:

- verify desktop and web layouts;
- verify loading, error, and empty states;
- include screenshots in the pull request.

## Backend changes

For backend changes:

- add regression coverage for bug fixes;
- verify approval and security-sensitive flows;
- document any environment or data migration requirements.

## Release checks

Before a release:

- confirm the changelog entry;
- confirm licensing and notices are current;
- verify download links and packaging artifacts;
- verify onboarding and auth flows still work.
