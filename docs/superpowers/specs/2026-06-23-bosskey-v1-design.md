# Bosskey v1 Design

Status: Approved for specification handoff

## Purpose

Bosskey v1 adds a strict physical-factor control layer to the BossCrafts ecosystem using a normal USB drive that carries BossCrafts-issued encrypted key material.

Its job is to protect:

- CBCAA/A.S.S. account and launch security
- A.S.S. product launch authorization where Bosskey is required
- local high-risk actions inside BossForgeOS and Runeforge

This is a production-minded v1 design focused on getting a workable, supportable hardware-style security flow into the product quickly without depending on dedicated FIDO2/PIV hardware.

## Core Decisions

The following decisions are locked for v1:

- Bosskey media is a normal USB drive
- one Bosskey per license
- one license per Bosskey
- Bosskey uses presence plus challenge-response
- protected routine actions use Bosskey only
- account/user-level changes require Bosskey plus command code
- no separate Bosskey PIN in v1
- lost Bosskey recovery is manual admin recovery

## Scope

Bosskey v1 covers three product areas:

1. CBCAA account authority
2. A.S.S. launch and protected service actions
3. BossForgeOS / Runeforge protected local actions

It should not be treated as an optional cosmetic security feature. It is a first-class authorization artifact.

## Security Model

Bosskey v1 is not just “USB inserted yes/no”. The software must verify:

1. the correct Bosskey package is present on the USB
2. the package belongs to the expected license/account context
3. the package can answer a fresh software-generated challenge

This means a copied file on the wrong path or stale cached state should not authorize an action by itself.

## Physical Media Model

Bosskey v1 uses standard removable USB storage.

Each valid Bosskey contains one BossCrafts-issued encrypted key package. That package is bound to:

- one license
- one account
- one Bosskey identity

The USB is therefore a dedicated artifact, not a multi-tenant carrier for multiple BossCrafts identities.

## Key Package Model

Each Bosskey package should contain:

- package identifier
- account identifier
- license identifier
- product scope
- issuance metadata
- encrypted secret material used for challenge-response
- integrity/signature metadata
- status markers such as revoked or rotated if needed

The package must be treated as encrypted sensitive material, not plaintext configuration.

## Authorization Modes

### Bosskey Only

Bosskey alone is sufficient for routine protected operational actions.

Examples:

- A.S.S. launch authorization where Bosskey is required
- local protected actions in BossForgeOS
- local protected actions in Runeforge
- routine operational confirmations that require physical possession but not identity-profile mutation

### Bosskey Plus Command Code

Account-level or user-level changes must require both:

- Bosskey
- command code

Examples:

- password change
- email change
- MFA reset
- license ownership changes
- Bosskey replacement approval
- device or identity-sensitive recovery actions
- admin-assisted identity modifications

This split keeps ordinary use practical while placing stronger friction around identity mutation and irreversible authority changes.

## Why No Bosskey PIN In v1

Bosskey v1 intentionally does not add a separate Bosskey PIN.

Reasons:

- lower user friction
- lower support burden
- fewer lockout paths
- simpler provisioning and recovery

The security model is already strong enough for v1 because it combines:

- physical USB possession
- encrypted challenge-response
- command code for identity-critical actions

If later needed, a Bosskey PIN can be introduced in v2 without changing the core artifact model.

## Challenge-Response Flow

Bosskey authorization should work like this:

1. the app detects candidate USB media
2. the app locates Bosskey package metadata
3. the app verifies package integrity and scope
4. the app generates a short-lived random challenge
5. the Bosskey package material is used to derive or sign a response
6. the software validates the response against expected cryptographic output
7. authorization succeeds only if the response is valid and fresh

This must be replay-resistant. A previous valid response must not authorize a later action.

## CBCAA Role

CBCAA is the source of authority for Bosskey issuance and lifecycle state.

CBCAA responsibilities in v1:

- issue Bosskey package records
- bind Bosskeys to license/account identity
- track Bosskey status
- support revocation
- support manual admin recovery/rebind
- enforce Bosskey-required flows for account-sensitive actions

CBCAA should be able to answer questions such as:

- which Bosskey belongs to this license
- is this Bosskey active
- has it been revoked
- has it been replaced

## A.S.S. Role

A.S.S. should treat Bosskey as the physical gate artifact for protected launch and service actions.

For v1, A.S.S. should be able to:

- detect Bosskey presence
- validate the package
- perform challenge-response
- request command code as an additional factor for account/user changes
- surface clear error states when Bosskey is missing, invalid, revoked, or mismatched

When A.S.S. is launching into other BossCrafts products, the Bosskey result should be carried into the launch-ticket or downstream session flow as appropriate.

## BossForgeOS / Runeforge Role

BossForgeOS and Runeforge should accept Bosskey as the physical authorization factor for local protected actions.

The v1 integration target is:

- high-risk operational actions can require Bosskey
- identity-changing/account-changing actions require Bosskey plus command code

This should align with existing command-code protected flows rather than bypassing them.

## Provisioning Model

Bosskey provisioning should be a deliberate issuance flow, not a generic file copy.

Recommended v1 flow:

1. admin or authorized issuance flow creates a Bosskey package for a specific license
2. package is written to the target USB
3. CBCAA records the Bosskey as active for that license
4. software can then use the USB for protected operations

The system must not assume arbitrary USB drives are valid just because they contain similarly named files.

## Revocation And Replacement

Bosskey v1 supports:

- revoke existing Bosskey
- issue replacement Bosskey
- rebind license to replacement Bosskey

Replacement is not self-serve in v1. It is manual admin recovery with identity checks.

This is the right v1 tradeoff because:

- it keeps the security bar high
- it avoids weak automated recovery loopholes
- it matches the one-key-per-license model

## Failure States

Bosskey flows must clearly distinguish at least these outcomes:

- no USB media detected
- Bosskey package missing
- wrong license/account scope
- package integrity invalid
- challenge-response failed
- Bosskey revoked
- Bosskey replaced
- command code additionally required

The software should not collapse all of these into a generic “Bosskey failed” message.

## Audit Requirements

All Bosskey-sensitive actions must generate audit events.

Required v1 event families:

- Bosskey detected
- Bosskey package validated
- Bosskey challenge issued
- Bosskey challenge passed
- Bosskey challenge failed
- Bosskey missing
- Bosskey revoked
- Bosskey replaced
- Bosskey-authorized protected action
- Bosskey plus command-code protected account change

These events should be visible to the relevant product and, where applicable, CBCAA admin tooling.

## Non-Goals

These should not delay v1:

- FIDO2 hardware support
- smart-card/PIV style hardware
- multi-key-per-license support
- multi-license-per-key support
- self-service replacement
- separate Bosskey PIN
- hidden partition or exotic USB media formatting

## Recommended v1 Implementation Shape

Bosskey v1 should be implemented as:

- a shared Bosskey package format and verifier
- CBCAA-side issuance and lifecycle records
- A.S.S.-side USB detection and challenge-response gate
- BossForgeOS / Runeforge-side protected action verifier

This keeps the artifact model consistent across the stack.

## Release Standard

Bosskey v1 is ready for release when we can reliably do all of the following:

1. issue a Bosskey package to one license
2. validate USB presence and package integrity
3. perform challenge-response successfully
4. reject replay or invalid responses
5. require Bosskey for protected operational actions
6. require Bosskey plus command code for account/user changes
7. support manual admin replacement and revocation

## Recommendation Summary

Build Bosskey v1 as a dedicated, single-license encrypted USB artifact with presence-plus-challenge-response verification, Bosskey-only protection for routine protected actions, and Bosskey-plus-command-code protection for account or user changes.

This is the strongest practical v1 design that still ships on normal USB media and works with the current CBCAA/A.S.S. release path.
