# API Contracts

## Principles

- Keep response shapes stable where possible.
- Version breaking contract changes explicitly.
- Document approval and error states, not just success responses.

## Areas that require care

- auth endpoints;
- chat request and response payloads;
- setup and onboarding endpoints;
- system status endpoints;
- tool event and thought log payloads.

## Change policy

If you change an API contract:

- update tests;
- update docs;
- note the change in the changelog if user-visible;
- call out migration impact in the pull request.
