# CBCAA v1 Design

Status: Approved for specification handoff

## Name

CBCAA: Central BossCrafts Account Authority

Canonical production host:

- `accounts.bosscrafts.net`

## Purpose

CBCAA is the central identity, entitlement, device-binding, and launch-ticket authority for BossCrafts software.

For the first release, its job is to unlock a paid-beta standalone release of A.S.S. by providing:

- account creation
- secure login
- TOTP-based second factor
- command-code enrollment and verification
- direct BossCrafts license entitlements
- Stripe checkout and webhook-driven activation
- per-device registration and enforcement
- launch-ticket issuance for A.S.S.

This version is intentionally optimized for fastest reliable path to revenue, not maximum platform breadth.

## Product Scope

CBCAA v1 is a dedicated standalone service and repository. It is not embedded inside BossForgeOS or A.S.S. because it will become shared infrastructure for multiple BossCrafts products.

The first supported product surface is:

- `A.S.S.` as a standalone launcher/service

CBCAA v1 must be sufficient for:

1. a user to create an account
2. a user to buy a paid entitlement directly from BossCrafts
3. A.S.S. to confirm the user identity and entitlement
4. A.S.S. to receive a short-lived launch ticket
5. A.S.S. to use that ticket to open BossCrafts software without repeating local login

## Explicit v1 Decisions

The following are locked in for v1:

- canonical host: `accounts.bosscrafts.net`
- deployment model: production-first hosted web service
- signup model: full secure signup on day one
- license source: direct BossCrafts account licenses
- payment processor: Stripe
- MFA: authenticator app TOTP
- command code: required during signup, not deferred
- A.S.S. launch flow: CBCAA-issued launch tickets

The following are explicitly deferred:

- Microsoft Store entitlement validation
- Bosskey USB support
- BridgeBase Alpha integration details
- multi-region deployments
- external auth SaaS as primary authority

## Architecture

CBCAA v1 should be a hosted monolith:

- one backend API
- one account/admin web surface
- one relational database
- one webhook entrypoint set

This is the right v1 shape because it minimizes operational complexity while keeping the whole account, entitlement, and launch flow under BossCrafts control.

Internally, the service should still be divided into clear modules:

- identity
- authentication
- MFA
- command-code verification
- device registration
- billing
- entitlements
- launch-ticket issuance
- audit logging
- admin support

## Recommended Stack

- `FastAPI`
- `PostgreSQL`
- `SQLAlchemy`
- `Alembic`
- `argon2` password hashing
- `pyotp` for TOTP enrollment and verification
- `Stripe` checkout + webhooks
- signed short-lived launch tickets using JWT or PASETO-style claims

Why this stack:

- FastAPI gives a clean API-first service shape
- PostgreSQL is mature and production-ready
- SQLAlchemy + Alembic provide migration control
- Argon2 is the strongest mainstream default for password hashing
- TOTP is a proven and user-understandable MFA path
- Stripe is the fastest route to automated paid access

## User Identity Model

Each user must have:

- email
- username
- password
- command code
- TOTP enrollment
- account verification status

### Password

- standard account password
- stored only as Argon2 hash
- never retrievable

### Command Code

The command code is a second secret under user control with these rules:

- at least 7 ordered words
- case-sensitive
- words separated by `*`
- no spaces

Example:

- `*Alpha*codex*Bravo*ember*Gate*Signal*North`

This should be stored as a protected verifier, not reversible plaintext.

### TOTP

Users must complete authenticator enrollment during signup.

The account is not fully activated until:

- email is verified
- TOTP is enrolled
- command code is successfully set

## Security and Verification Rules

### Login

Primary login flow:

1. username or email + password
2. TOTP challenge
3. entitlement/device context evaluation

### Command Code Usage

The command code must be required:

- during account setup validation
- on every new device registration
- before sensitive account changes
- before support-level or security-sensitive operations

Examples of sensitive operations:

- changing email
- changing password
- resetting MFA
- inspecting license/device state
- revoking devices

### New Device Rule

On a new device, successful password login is not enough. The user must also pass:

- TOTP
- command code challenge

Only then may the device be registered for that account.

## Device and License Model

### License Policy

The current policy chosen by the user is:

- one license, one device
- multiple licenses allow simultaneous logins

CBCAA therefore needs to model:

- account
- product entitlement
- device registrations
- active seat consumption

For v1, the first product entitlement should support:

- free A.S.S. tier with capped/small transfers
- paid A.S.S. tier with no cap

### Device Registration

Each device record should include:

- device id
- account id
- product id
- first seen timestamp
- last seen timestamp
- status
- seat-consuming flag
- trust evidence / registration method

### Enforcement

Before issuing a launch ticket for A.S.S., CBCAA must verify:

- the account is active
- the entitlement exists
- the entitlement permits requested product access
- the device is registered
- the device does not violate seat count rules

## Billing and Entitlements

Stripe is the v1 source of paid license activation.

### Required Billing Behavior

- create checkout sessions for paid A.S.S. upgrade
- receive webhook confirmation from Stripe
- activate or upgrade entitlement after successful payment
- support free-to-paid transition
- support admin-side manual correction if webhook delivery or state drifts

### Entitlement States

Each entitlement should track:

- product
- plan/tier
- status
- start time
- renewal/cancellation markers if applicable
- linked Stripe customer/subscription/payment identifiers

For v1, a one-time or simple recurring paid plan is acceptable as long as the entitlement engine is general enough to expand.

## A.S.S. Launch-Ticket Flow

CBCAA exists partly to serve as the authority behind the A.S.S. launch flow.

### Required Flow

1. user opens A.S.S.
2. A.S.S. sends user to CBCAA login/signup flow
3. CBCAA authenticates the user
4. CBCAA verifies entitlement and device rights for A.S.S.
5. CBCAA issues a short-lived signed launch ticket
6. A.S.S. exchanges that ticket for a product session
7. A.S.S. can then launch BossForgeOS or other BossCrafts software without repeating local login

### Launch Ticket Requirements

Launch tickets must be:

- short-lived
- signed
- product-scoped
- device-scoped
- single-use or replay-protected

Each ticket should include claims such as:

- ticket id
- account id
- username
- target app
- device id
- entitlement tier
- issued at
- expiration

## Admin and Support Surface

CBCAA v1 needs a minimal admin/operator surface so you can actually run the beta.

Required capabilities:

- inspect user accounts
- inspect device registrations
- inspect entitlement state
- inspect payment/license linkage
- revoke devices
- correct stuck entitlement state
- issue/revoke manual support licenses if needed
- view audit events

This does not need to be pretty in v1, but it must exist.

## Audit Logging

Every important security and commercial action must emit an audit event.

Required audit event families:

- signup started/completed
- email verification
- password login success/failure
- TOTP challenge success/failure
- command-code verification success/failure
- device registration
- device revocation
- checkout created
- Stripe webhook processed
- entitlement granted/changed/revoked
- launch ticket issued
- launch ticket rejected/replayed/expired

## Repository Shape

Recommended new repository root:

- `I:\Bosscrafts\CBCAA`

Recommended top-level layout:

- `app/`
- `frontend/`
- `migrations/`
- `tests/`
- `docs/`
- `scripts/`
- `deploy/`

Recommended backend module layout:

- `app/api/`
- `app/auth/`
- `app/accounts/`
- `app/command_codes/`
- `app/devices/`
- `app/entitlements/`
- `app/billing/`
- `app/tickets/`
- `app/admin/`
- `app/audit/`
- `app/db/`
- `app/models/`
- `app/schemas/`

## v1 Release Boundary

CBCAA v1 is considered release-sufficient for A.S.S. beta when it can:

1. create and verify accounts
2. enforce password + TOTP + command code
3. register and enforce device access
4. activate paid entitlements through Stripe
5. issue valid launch tickets for A.S.S.
6. expose enough admin controls to recover/support users

It is not necessary for v1 to solve every future BossCrafts product need.

## Non-Goals

These should not delay v1:

- Bosskey USB integration
- Microsoft Store billing sync
- full BridgeBase Alpha support
- advanced multi-tenant enterprise licensing
- polished consumer-grade account portal aesthetics
- generalized plugin architecture

## Recommended Implementation Order

1. scaffold new repo
2. build data model + migrations
3. build signup/login/TOTP/command-code flow
4. build device registration + enforcement
5. build Stripe checkout + webhook processing
6. build entitlement resolution
7. build launch-ticket issuance
8. build minimal admin surface
9. wire A.S.S. to consume CBCAA

## Risks To Watch

- overbuilding beyond A.S.S. beta needs
- storing command-code material too weakly
- weak replay protection on launch tickets
- device identity being too easy to spoof
- entitlement drift between Stripe and local records
- support dead-ends if admin tooling is missing

## Recommendation Summary

Build CBCAA v1 as a standalone hosted monolith at `accounts.bosscrafts.net` with FastAPI, PostgreSQL, Stripe, TOTP MFA, command-code enforcement, device-bound entitlements, and short-lived signed launch tickets for A.S.S.

This is the fastest path to a real paid beta while preserving BossCrafts control over identity, licensing, and future product launch flows.
