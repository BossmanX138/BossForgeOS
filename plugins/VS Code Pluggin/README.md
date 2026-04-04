# BossForgeOS VS Code Extension

## Table of Contents

- [Status Bar Health Indicator (Planned)](#status-bar-health-indicator-planned)
- [Onboarding Wizard](#onboarding-wizard)

## Status Bar Health Indicator (Planned)

A status bar item will be added to the extension to display BossForgeOS health:
- **Online**: Agent is connected and responsive on the bus.
- **Stale**: Agent is connected but not recently active.
- **Offline**: Agent is not connected or unreachable.

The status bar will update in real time by reading agent state from the bus.

**Implementation To-Do:**
- Register a status bar item in `extension.js`.
- Poll or subscribe to agent state from the bus.
- Update the status bar item text and color based on health.

---

## Onboarding Wizard
- Accessible via command: "BossForgeOS: Onboarding Wizard"
- Sidebar panel in Activity Bar
- Placeholder UI for secrets, tokens, and voice profile

---

_Last updated: March 30, 2026 by Archivist_
