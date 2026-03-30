# BossForgeOS Blueprint Gap Backlog

This backlog maps currently missing Blueprint features to an execution order.

## Priority Bands

- P0: Core runtime capabilities that unlock other Blueprint features.
- P1: High-value integrations and user-facing tooling.
- P2: Advanced interaction and ecosystem expansion.

## P0 - Core Runtime Integrations

### P0.1 GitHub Connector Service
- Status: Not implemented.
- Goal: Add a dedicated connector for issue/PR/repo workflows beyond raw git push.
- Scope:
  - Connector module in core.
  - Bus commands for create issue, list/open PRs, repo sync status.
  - Security Sentinel token consumption.
  - Control Hall panel actions.
- Depends on: security token flow (already present as base).
- Acceptance:
  - Commands execute through bus and emit result events.
  - Token is not printed in logs/events.

### P0.2 Hugging Face Connector Service
- Status: Not implemented.
- Goal: Manage HF model search/download/list through BossForge bus.
- Scope:
  - Connector module in core.
  - Commands for search, download, list local models.
  - Config state in bus/state.
  - Control Hall panel.
- Depends on: Security Sentinel secret storage for HF token.
- Acceptance:
  - Search/download/list callable from CLI and Control Hall.

### P0.3 Webhook Listener Service
- Status: Not implemented.
- Goal: Receive external events into Rune Bus.
- Scope:
  - Lightweight HTTP listener with optional shared secret validation.
  - Event normalization into bus/events.
  - Basic replay protection and size limits.
- Depends on: none.
- Acceptance:
  - Verified inbound webhook appears as normalized event in bus/events.

### P0.4 Model-Keeper Compatibility Layer
- Status: Missing as named BP component.
- Goal: Introduce model_keeper service identity and command compatibility while reusing Model Gateway internals.
- Scope:
  - Wrapper service and state key model_keeper.
  - Alias commands in CLI.
  - Launcher support.
- Depends on: none.
- Acceptance:
  - model_keeper appears alive and responds to status_ping.

## P1 - Editor + Distribution

### P1.1 VS Code Extension Project
- Status: Not implemented.
- Goal: Ship a working extension project with commands/views bound to Rune Bus.
- Scope:
  - extension folder with package manifest and activation commands.
  - Event stream and command dispatch actions.
  - Agent sidebar, endpoint management, ritual runner, and inline actions.
  - Command palette entries and WebSocket bridge for live event updates.
  - Mythic UI layer (animated sigils / forge-ember styling).
- Depends on: P0 webhook and connector APIs preferred but not strictly required.
- Acceptance:
  - Extension loads locally and dispatches at least one bus command.

### P1.2 VS Code Extension Packaging/Install Path
- Status: Not implemented.
- Goal: Build and installable package flow.
- Scope:
  - VSIX packaging scripts.
  - Optional install helper script.
  - Auto-install option for local VS Code instance.
- Depends on: P1.1.
- Acceptance:
  - Generated VSIX installs and runs expected command.

## P3 - Documentation/Spec Artifacts (From VoiceLayer Export)

### P3.1 Voice Layer Formal Spec Pack
- Status: Not implemented.
- Goal: Produce the formal documentation pack requested in the VoiceLayer export.
- Scope:
  - Title page.
  - Cover design.
  - Formal executive summary.
  - Requirements matrix.
  - System architecture diagram (text-based).
  - Hyperlinked table of contents in a Word-ready format.
- Depends on: none.
- Acceptance:
  - Docs compile into a coherent, navigation-friendly technical specification.

## P2 - Voice Layer (Blueprint A-J)

### P2.1 Listener Daemon (ASR entry)
- Status: Not implemented.
- Goal: Wake phrase + transcription event emitter.

### P2.2 Speaker Daemon (TTS output)
- Status: Not implemented.
- Goal: TTS output routed by agent persona.

### P2.3 Voice Orchestrator
- Status: Not implemented.
- Goal: Parse voice command grammar and route to bus commands.

### P2.4 Voice Grammar and Ritual Mapping
- Status: Not implemented.
- Goal: Deterministic grammar for rituals/model/control workflows.

### P2.5 Voice Workflows for GitHub/HF/VS Code
- Status: Not implemented.
- Goal: End-to-end spoken workflows using P0/P1 foundations.

## Recommended Execution Order

1. P0.1 GitHub Connector Service
2. P0.2 Hugging Face Connector Service
3. P0.3 Webhook Listener Service
4. P0.4 Model-Keeper Compatibility Layer
5. P1.1 VS Code Extension Project
6. P1.2 VS Code Extension Packaging
7. P2 voice stack in sequence (P2.1 to P2.5)

## Suggested First Sprint (3-5 days)

- Deliver P0.1 and P0.3 together:
  - GitHub connector command surface.
  - Webhook listener ingestion.
  - Control Hall mini panel for GitHub quick ops.
  - Unit tests for command parsing and auth guardrails.
