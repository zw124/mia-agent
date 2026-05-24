# Security Model

## Core assumptions

- the app may invoke local and remote tools;
- approvals and visibility matter as much as raw capability;
- tool execution must be auditable;
- secrets and privileged operations must be separated from ordinary chat state.

## Control layers

- auth and user identity;
- approval gates;
- runtime policy checks;
- logs and traceability;
- contributor review and CI protections.

## High-risk areas

- computer-use flows;
- browser automation with side effects;
- remote service tokens;
- update and packaging pipelines.
