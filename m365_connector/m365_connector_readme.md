# M365 Connector README

Canonical subsystem readme for `m365_connector`.

## Purpose

Implements Microsoft 365 connector services used by BossForgeOS.

## Current State

- Connector hosts MCP server logic and action handlers for Microsoft 365 integrations.
- Runtime dependencies and service behavior details remain partially distributed across connector docs.

## Growth Opportunities

- Track service-by-service readiness and authentication hardening status.
- Keep a permissions map for each implemented action family.

## TODO

- Add a readiness matrix for Outlook, Teams, OneDrive, Calendar, Access, and OneNote.
- Add per-action Graph permission requirements and known limitations.
