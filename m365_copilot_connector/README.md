# BossCrafts_Devlot_MkII Official Microsoft Ambassador Runtime

This runtime merges BossCrafts_Devlot_MkII with Microsoft 365 service access (Outlook, Teams, OneDrive, Calendar) via Model Context Protocol (MCP) and designates him as the official BossCrafts ambassador for Microsoft ecosystem topics.

## Table of Contents

- [Features](#features)
- [Structure](#structure)
- [Merge Notes](#merge-notes)
- [Required Environment Variables](#required-environment-variables)
- [Graph API Permissions (Application)](#graph-api-permissions-application)
- [Setup](#setup)
- [Extension Points](#extension-points)
- [Implementation Status](#implementation-status)

## Features

- Merged Devlot + M365 runtime identity
- Official BossCrafts ambassador role for Microsoft ecosystem decisions and integrations
- Read/send Outlook emails via Microsoft Graph (implemented)
- Access/send Teams messages
- Access calendar events
- File operations on OneDrive
- Declarative agent configuration for Copilot
- Extension points for BossForgeOS agent orchestration

## Structure

- `mcp_server.py`: MCP server entry point
- `actions/`: Action handlers for each M365 service
- `declarativeAgent.json`: Declarative config for Copilot
- `ai-plugin.json`: Plugin manifest
- `mcp.json`: MCP manifest

## Merge Notes

- Runtime identity is defined as `BossCrafts_Devlot_MkII (M365 Runtime)` in MCP/declarative manifests.
- Added extension hook: `DevlotAutonomyHooks` for TODO automation and recommendation events.

## Required Environment Variables

- `M365_TENANT_ID`: Microsoft Entra tenant id
- `M365_CLIENT_ID`: App registration client id
- `M365_CLIENT_SECRET`: App registration client secret
- `M365_MAILBOX_USER`: Mailbox user principal name or object id used for `/users/{id}` Graph calls

## Graph API Permissions (Application)

- `Mail.Read`
- `Mail.Send`

After adding permissions on the app registration, grant admin consent for the tenant.

## Setup

1. Install requirements: `pip install -r requirements.txt`
2. Configure the required environment variables
3. Run: `python mcp_server.py`

## Extension Points

- Add new action handlers in `actions/`
- Integrate with BossForgeOS orchestration via provided hooks

## Implementation Status

- Outlook `readEmail`: implemented with live Graph API calls
- Outlook `sendEmail`: implemented with live Graph API calls
- Teams/Calendar/OneDrive actions: scaffolded placeholders ready for Graph integration
