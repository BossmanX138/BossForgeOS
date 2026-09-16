# BossGate Agent View Disclosure Design

## Scope

This design completes `BG-010`: agent code and proprietary profile information remain hidden by default, while authenticated proprietary software may render an individual agent's approved profile view when that agent is explicitly configured as non-hidden.

This setting controls views only. It does not disable encryption, rewrite historical packages, expose plaintext files, or alter travel behavior.

## Security Invariants

1. New agents default to a `hidden` disclosure posture.
2. Agent gate companion files remain encrypted for every agent.
3. BossGate travel packages remain encrypted at rest and in transit for every agent.
4. Historical packages are immutable and are never rewritten when posture changes.
5. A non-hidden posture never grants raw filesystem disclosure.
6. Unauthenticated or untrusted viewers receive a sealed summary regardless of posture.

## Agent Profile State

Each agent profile stores:

```json
{
  "disclosure_posture": "hidden"
}
```

Allowed values:

1. `hidden`
2. `non_hidden`

Missing or invalid values normalize to `hidden`.

The existing `encrypt_profile` creation input is migrated away from controlling BossGate encryption. If retained for compatibility, it is interpreted only as a disclosure preference:

1. `encrypt_profile=true` maps to `disclosure_posture=hidden`.
2. `encrypt_profile=false` maps to `disclosure_posture=non_hidden`.

`bossgate_enabled` remains a travel capability setting. It is not disabled merely because an agent is non-hidden.

## Trusted Viewer Channels

The initial trusted viewer channels are:

1. `bossforgeos`
2. `agentforge_standalone`

The configurable viewer registry also includes:

1. `bridgebase_alpha`

`bridgebase_alpha` is disabled by default until its trust policy is approved.

## View Rules

AgentForge exposes a profile-view operation that accepts:

1. Agent name
2. Authenticated viewer identity
3. Viewer channel

The view operation returns one of two shapes.

### Sealed Summary

Returned when the agent is hidden, the viewer is unauthenticated, or the viewer channel is not enabled:

```json
{
  "agent": "agent-name",
  "disclosure_posture": "hidden",
  "sealed": true,
  "secure_address": "*seven*word*bossgate*address*goes*right*here*"
}
```

The summary must not include code, prompts, skills, tools, endpoint details, or proprietary profile fields.

### Approved Profile View

Returned only when the agent is non-hidden and the authenticated viewer channel is enabled:

```json
{
  "agent": "agent-name",
  "disclosure_posture": "non_hidden",
  "sealed": false,
  "profile": {
    "...": "approved persisted profile fields"
  }
}
```

This is a rendered application response. It does not decrypt or publish gate files and does not change package contents.

## AgentForge Controls

AgentForge owns disclosure-posture management.

1. Creation defaults to hidden.
2. The creation form exposes a hidden-profile checkbox enabled by default.
3. Existing agents may switch between `hidden` and `non_hidden`.
4. Posture changes affect future views of that agent only.
5. Posture changes persist to the agent profile and preserve the encrypted gate companion.

The existing UI label `Encrypt profile` should be replaced with wording that reflects view disclosure, such as `Hide proprietary profile details`.

## BossGate Packaging

BossGate packaging remains encrypted for every package.

Package metadata visibility defaults to `none`. A package request cannot use the agent-level non-hidden posture as permission to emit plaintext metadata into package documents. Package metadata disclosure remains deny-by-default and may only be expanded later through an explicit package policy.

For `BG-010`, the agent-level posture governs AgentForge profile views only.

## Error Handling

1. Unknown agent names return `agent not found`.
2. Invalid posture values return a validation error on update.
3. Missing viewer identity produces a sealed summary.
4. Unknown or disabled viewer channels produce a sealed summary.
5. Gate-file refresh failures return an error and do not persist a posture change.

## Test Coverage

Automated tests must verify:

1. New agents default to `hidden`.
2. Compatibility input `encrypt_profile=false` maps to `non_hidden` without disabling BossGate.
3. Posture updates can move an existing agent in both directions.
4. Gate files remain encrypted after posture changes.
5. Hidden agents return sealed summaries to trusted viewers.
6. Non-hidden agents return approved profile views to authenticated `bossforgeos` and `agentforge_standalone` viewers.
7. Unauthenticated viewers receive sealed summaries.
8. `bridgebase_alpha` viewers receive sealed summaries while the channel remains disabled.
9. BossGate package encryption remains active regardless of disclosure posture.
10. Package metadata remains `none` unless a separate explicit package policy is introduced.

## Documentation Updates

Update:

1. `docs/bossgate_connector.md`
2. `docs/bossgate_protocol.md`
3. `docs/bossgate_connector_todo.md`
4. `docs/AgentForge_readme.md`

Mark `BG-010` complete only after the relevant automated suites pass.
