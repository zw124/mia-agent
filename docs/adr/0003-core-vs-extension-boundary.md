# ADR 0003: Core vs extension boundary

## Status

Accepted

## Decision

Core user-facing capabilities, approval paths, and security logic should remain clearly documented in the public repository. Extensions and integrations must expose explicit boundaries.

## Rationale

This reduces confusion around what is community-maintained, what is provider-specific, and what may belong in a different licensing tier.
