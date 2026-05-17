---
version: alpha
name: Mia Agent Design System
description: Stable design baton for Mia surfaces and generated product artifacts.
colors:
  background: "#0F0F0D"
  surface: "#171714"
  surfaceRaised: "#20201C"
  text: "#F2F0EA"
  muted: "#A5A29A"
  border: "#34332D"
  accent: "#F2F0EA"
  success: "#4BA36A"
  warning: "#C9933A"
  danger: "#D35F5F"
typography:
  display:
    fontFamily: "Geist Sans"
    fontSize: 56px
    fontWeight: 520
    lineHeight: 1.04
  body:
    fontFamily: "Geist Sans"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.55
  mono:
    fontFamily: "Geist Mono"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
rounded:
  sm: 6px
  md: 10px
  lg: 16px
spacing:
  xs: 6px
  sm: 10px
  md: 16px
  lg: 28px
  xl: 48px
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#10100E"
    rounded: "{rounded.lg}"
    padding: 12px 18px
  panel:
    backgroundColor: "{colors.surface}"
    borderColor: "{colors.border}"
    rounded: "{rounded.lg}"
  chat-input:
    backgroundColor: "{colors.surfaceRaised}"
    borderColor: "{colors.border}"
    rounded: "{rounded.lg}"
---

# Overview

Mia design work should feel like a serious operator interface: quiet, dense, fast, and easy to understand. The default visual reference is Cursor-like restraint, not consumer SaaS decoration. Use visual hierarchy, spacing, typography, and state design instead of gradients, emojis, oversized cards, or generic AI-dashboard patterns.

# Colors

Use neutrals as the system backbone. Accent color should usually be text/foreground contrast, not a loud brand color. Add a stronger accent only when the user gives a brand direction or the artifact type genuinely needs it.

# Typography

Prefer precise product typography with clear size ramps. Do not use default browser/system stacks unless matching an existing app. Use monospace only for code, logs, model/tool traces, identifiers, and terminal-like content.

# Layout

Design for high-signal workflows first: chat, setup, status, approvals, logs, memory, and tool traces. Desktop layouts should preserve density without feeling cramped. Mobile layouts should collapse into a single clear flow with sticky primary actions when needed.

# Components

Core components are chat threads, composer, setup steps, status cards, approval gates, tool logs, data tables, and compact navigation. Each component needs loading, empty, error, disabled, and offline states when it can receive async data.

# Interaction

Interactions should be useful, not decorative. Prefer keyboard access, visible focus, compact hover states, inline validation, and clear pending states. Avoid motion that slows down agent workflows.

# Do's And Don'ts

Do use tokens and repeated component rules instead of one-off styling. Do preserve existing product voice and structure during revisions unless the user asks for a redesign. Do verify contrast, responsive behavior, and real content density.

Do not invent brand values from memory. Do not produce wireframes when the user asks for a finished product surface. Do not add glassmorphism, purple gradients, or playful decoration unless explicitly requested.
