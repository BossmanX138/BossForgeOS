# BossGate v1 Platform Requirements

## Purpose

This document defines what BossGate must provide before BossCrafts can
truthfully say that its forges and connected systems "speak BossGate."

It complements, but does not replace:

1. [bossgate_protocol.md](./bossgate_protocol.md)
2. [bossgate_connector.md](./bossgate_connector.md)
3. [bossgate_connector_todo.md](./bossgate_connector_todo.md)

Those documents describe transport, commands, and implementation status. This
document defines the platform contract.

## Platform Claim

A system speaks BossGate only when it:

1. Carries a BossGate identity.
2. Implements the required BossGate runtime module.
3. Uses the canonical BossGate handshake, envelope, and audit semantics.
4. Enforces BossGate authorization and protected-action policy.
5. Fails closed when trust, policy, or entitlement checks do not pass.

If a system requires one-off adapters, ad hoc trust rules, or bypasses local
policy enforcement, it is not fully BossGate-native.

## Compatibility Tiers

BossCrafts systems should be classified explicitly:

1. `bossgate_native`
   - Implements the full BossGate runtime contract.
   - Can initiate or receive BossGate sessions according to policy.
   - Enforces the canonical authorization and audit model locally.
2. `bossgate_connected`
   - Connects through a BossGate adapter or connector.
   - Can exchange approved BossGate envelopes.
   - Relies on an adapter for part of the runtime contract.
3. `bossgate_observable`
   - Emits telemetry or presence into the BossGate map.
   - Cannot perform full BossGate transport or protected actions.

BossCrafts should not describe `bossgate_connected` or `bossgate_observable`
systems as fully speaking BossGate without the qualifier.

## Authority Split

BossGate v1 depends on a clean separation of authority.

### CBCAA

`CBCAA` at `accounts.bosscrafts.net` is the hosted authority for:

1. Human account identity.
2. License ownership and entitlement state.
3. Billing-backed activation and revocation.
4. Account recovery and support-admin recovery workflows.
5. Launch tickets or other signed short-lived authorization artifacts.

### BossGate

BossGate is the runtime trust and transport layer for:

1. Endpoint identity and gate address.
2. Peer discovery and reachability.
3. Secure session establishment.
4. Encrypted message, file, voice, and control transport.
5. Local policy enforcement hooks.
6. Audit, telemetry, and transfer history.

### Bosskey

Bosskey is the local high-assurance factor for sensitive actions:

1. Possession proof.
2. Presence and challenge-response proof.
3. Per-license binding enforcement.
4. Manual admin recovery and rebind workflow.

### Authority Rule

CBCAA answers "who is this and what are they entitled to?"

BossGate answers "is this runtime endpoint trusted and is this operation
allowed right now?"

Bosskey answers "is the local operator physically and intentionally present for
this protected action?"

## Required Identity Model

Every BossGate-native forge or agent must have:

1. A stable BossGate identity.
2. A secure 7-word gate address.
3. A cryptographic key identity used for BossGate trust.
4. A machine or endpoint record.
5. An owner or operator relationship.
6. A capability declaration.
7. A policy binding and revocation path.

Identity must survive transport and reinstall without becoming detached from
its audit history.

## Required Runtime Module

Every BossGate-native system must embed a BossGate runtime module that
provides:

1. Gate identity bootstrap and validation.
2. Keyring or trust-store access.
3. Discovery, beaconing, and peer normalization.
4. Handshake and preflight orchestration.
5. Session establishment and encrypted transport.
6. Standard envelope encode/decode behavior.
7. Resume, replay-protection, and move-semantics support.
8. Audit event emission with correlation ids.
9. Local authorization and deny-reason enforcement.
10. Capability advertisement and version reporting.
11. Revocation, quarantine, and fail-closed handling.

This runtime module is the minimum bar for saying a forge speaks BossGate.

## Canonical BossGate Session Flow

BossGate-native systems must share the same high-level flow:

1. Discover or resolve the target gate.
2. Validate target eligibility and scope.
3. Run preflight and trust checks.
4. Establish a secure session.
5. Complete any required protected-action checks.
6. Delay payload release until the gate is open and ready.
7. Emit canonical lifecycle and audit events.
8. Retire or resume according to move and checkpoint rules.

The existing A.S.S. activation rule remains canonical for payload release:
handshake may happen during activation, but message, voice, file, or install
payloads do not begin until the gate is fully open.

## Authorization Model

BossGate-native systems must distinguish clearly between:

1. Transport trust.
2. Human/operator authorization.
3. Agent-skill authorization.
4. License and entitlement authorization.
5. Protected-action confirmation.

Successful transport trust alone must never imply permission to execute a
sensitive action.

## Protected-Action Policy

BossGate v1 still needs one final top-level decree before implementation is
complete:

1. `bosskey_only`
2. `bosskey_plus_command_code`

Until that is finalized, every BossGate-protected action matrix must mark the
confirmation rule explicitly rather than implying one.

At minimum, the policy matrix must classify actions across:

1. `read_only_telemetry`
2. `ordinary_authenticated_operation`
3. `license_sensitive_operation`
4. `system_sensitive_operation`
5. `security_admin_operation`
6. `destructive_or_irreversible_operation`

Each class must define:

1. Required human role or agent skill.
2. Whether CBCAA entitlement must be checked.
3. Whether Bosskey is required.
4. Whether command-code confirmation is required.
5. Required audit event set.
6. Failure behavior.

## Compliance Checklist

A forge may be called BossGate-native only when it can prove:

1. It advertises a BossGate identity and version.
2. It can complete canonical BossGate handshake and preflight.
3. It can exchange canonical encrypted BossGate envelopes.
4. It enforces local authorization and protected-action policy.
5. It records canonical audit events with deny reasons.
6. It honors revocation, expiry, and replay protection.
7. It supports fail-closed behavior for trust or policy failure.
8. It can be classified in the BossGate map without custom interpretation.

## Initial Native Targets

BossGate v1 should treat these as the first native targets:

1. `BossForgeOS`
2. `A.S.S.`
3. `bridgebase_alpha`

Other systems should be treated as `bossgate_connected` or
`bossgate_observable` until they satisfy the native contract.

## Immediate BossGate v1 Gaps

Before BossCrafts can claim broad BossGate-native interoperability, the repo
still needs:

1. A frozen authority contract across CBCAA, BossGate, and Bosskey.
2. A canonical protected-action matrix for BossForgeOS, A.S.S., Runeforge, and
   Control Hall.
3. A documented BossGate runtime module contract every forge must embed.
4. A declared compatibility/version profile for BossGate-native systems.
5. Acceptance tests that verify the compliance checklist on each native forge.

## Recommended Implementation Order

1. Finalize the authority split and protected-action decree.
2. Publish the BossGate runtime module contract and compatibility profile.
3. Add forge-by-forge compliance checklists for BossForgeOS, A.S.S., and
   `bridgebase_alpha`.
4. Align command, protocol, and UI flows to the protected-action matrix.
5. Add acceptance tests proving each native forge speaks BossGate without
   special-case logic.

## Non-Claim Rule

BossCrafts should not claim "everything speaks BossGate" until each target
system has been classified and verified against this document.
