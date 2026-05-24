---
version: opencode-dark-v1
name: Mia Opencode Operator Design System
description: Canonical visual guideline for all Mia app, desktop, dashboard, setup, and generated UI surfaces.
colors:
  background: "#0C0C0E"
  surface: "#161618"
  surfaceRaised: "#1C1C1F"
  border: "#38383A"
  borderMuted: "#2C2C2E"
  text: "#F4F4F5"
  textSecondary: "#C7C7CC"
  textMuted: "#8E8E93"
  textDim: "#68686F"
  accent: "#DFF9A6"
  danger: "#FF8F7A"
typography:
  mono:
    fontFamily: '"Berkeley Mono", "IBM Plex Mono", "SF Mono", SFMono-Regular, ui-monospace, monospace'
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.65
  small:
    fontFamily: '"Berkeley Mono", "IBM Plex Mono", "SF Mono", SFMono-Regular, ui-monospace, monospace'
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
radius:
  control: 6px
  panel: 8px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 18px
  xl: 24px
---

# Mia Visual Direction

Mia uses an opencode-style operator interface: dark, compact, fast, mono-first, and intentionally quiet. The UI should feel like a serious local agent console, not a consumer SaaS dashboard, iMessage clone, glassmorphism app, or Manus-style landing page.

# Core Rules

- Use the dark token set above for all app surfaces.
- Use mono typography for chat, navigation, settings, startup screens, tool traces, and status text.
- Use the real Mia logo from `apps/dashboard/public/mia-logo.png`; do not use blue dots or generic brand circles.
- Prefer open layouts and text hierarchy over cards. Use panels only when a boundary is required.
- Use 1px borders, no decorative shadows, no gradients, no glass, no oversized rounded cards.
- Radius is limited to `6px` for controls and `8px` for panels.
- Accent color is `#DFF9A6` and should be used sparingly for prompts, active states, and focus.
- Do not use purple, bright blue brand dots, white splash screens, serif hero titles, or glossy enterprise styling.

# Chat UI

- User messages should read like terminal input: prefix with `>` in accent color.
- Assistant messages should be plain text/Markdown on the dark background, not bubbles.
- Markdown must render cleanly: paragraphs, lists, code, pre blocks, tables, links, and blockquotes.
- Code blocks use dark raised panels with muted borders.
- Composer is a compact dark input with a thin border and small send control.
- Empty states should be short and calm, not marketing copy.

# Thinking UI

- Thinking state must be tiny and quiet: use lowercase `thinking`.
- Do not show a large assistant placeholder saying “Mia is thinking”.
- The thinking label uses 12px mono text in dim/muted color.
- The spinner should be small and use the accent color.
- Expanded thought logs should be compact, borderless, and aligned with the assistant message.
- Completed state can read `completed (n steps)` in the same small style.

# Settings And Startup

- Login, setup, settings, and Electron startup screens must use the same opencode dark theme.
- Startup screen should say what service is starting in direct language, using the Mia logo and compact panel.
- Settings cards should be simple dark panels with 1px muted borders.
- External integrations are optional relays; do not position Mia as iMessage-centered.

# Copy

- Use direct product language: “Mia”, “local runtime”, “agent service”, “message relay”, “settings”.
- Avoid “control center”, “iMessage-first”, “beautiful glass”, “enterprise”, and other old positioning.
- Error copy should say what failed and what to do next.

# Non-Negotiables

- Future UI changes must preserve this style unless the user explicitly requests a new direction.
- Any new app page must reuse the same tokens before adding new colors or visual effects.
- If a component feels like a generic AI dashboard card, simplify it.
