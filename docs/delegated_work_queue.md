# Delegated Work Queue

Date: 2026-03-10

This queue delegates non-extension backlog work while primary focus shifts to VS Code extension editing.

## Active Delegations

1. Agent: codemage
- Objective: Build GitHub connector service (P0.1).
- Deliverables:
  - core connector module
  - bus commands (create issue, list/open PRs, repo sync status)
  - CLI binding and Control Hall actions
  - auth + error unit tests
- Acceptance:
  - Commands emit result events on Rune Bus
  - No token leaks in logs/events

2. Agent: security_sentinel
- Objective: Secret and policy guardrails for connectors/webhooks.
- Deliverables:
  - shared token retrieval policy
  - redaction hooks for events/logging
  - webhook shared-secret validation rules
- Acceptance:
  - plaintext secrets absent from state/events/log outputs

3. Agent: runeforge
- Objective: Webhook listener service (P0.3).
- Deliverables:
  - HTTP listener endpoint
  - payload size limits and replay protection
  - normalized ingress events into Rune Bus
- Acceptance:
  - valid webhook creates normalized event
  - invalid signature/replay rejected safely

4. Agent: devlot
- Objective: Hugging Face connector service (P0.2).
- Deliverables:
  - search/download/list command surface
  - config/state persistence in bus state
  - CLI and Control Hall panel support
- Acceptance:
  - search/download/list callable from CLI + Control Hall

5. Agent: codemage
- Objective: Model-Keeper compatibility layer (P0.4).
- Deliverables:
  - model_keeper wrapper identity
  - launcher + CLI alias support
  - status/state compatibility tests
- Acceptance:
  - model_keeper responds to status_ping and appears in status views

## Sequencing Guidance

1. model_keeper compatibility
2. webhook listener
3. GitHub connector
4. Hugging Face connector
5. voice-layer prep contracts
