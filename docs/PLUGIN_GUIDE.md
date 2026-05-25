# Plugin Guide

## Goal

Plugins and integrations must have explicit trust, permission, and data-flow boundaries.

## Minimum expectations

- define what the plugin can read and write;
- define required credentials and scopes;
- define whether approval is required before execution;
- define failure behavior and audit logging needs.

## Community boundary

Avoid merging plugin designs that create hidden proprietary dependencies inside core community code without documenting the boundary first.
