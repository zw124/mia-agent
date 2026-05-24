# Release Process

## Before release

1. Update `CHANGELOG.md`.
2. Confirm `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`.
3. Run:

```bash
npm run typecheck
npm run build
npm run test
```

4. Build desktop artifacts as needed.
5. Confirm download URLs and update feeds.

## Release publication

- create a Git tag;
- publish release notes;
- upload desktop artifacts if applicable;
- verify production deployment health.

## After release

- watch issue intake;
- confirm update feeds;
- document hotfixes if required.
