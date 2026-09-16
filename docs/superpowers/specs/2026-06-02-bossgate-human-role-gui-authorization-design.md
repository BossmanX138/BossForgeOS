# BossGate Human Role And GUI Authorization Design

## Scope

This design completes `BG-011`: BossGate sensitive actions are gated by human roles or agent skills, and human users receive Control Hall interface mechanisms matching their assigned responsibilities.

Licensing implementation remains tracked by `BG-017` through `BG-021`. Remote-debug session transport remains tracked by `BG-022` through `BG-025`. This design creates permission-aware Commerce and Support workspaces now without falsely claiming those later command surfaces exist.

## Human Role Registry

Persist a local registry at:

```text
bus/state/bossgate_human_roles.json
```

The registry contains:

1. Seeded roles
2. Custom roles
3. Human-user role assignments
4. Bootstrap owner identity

Users may hold multiple roles. Effective permissions are the union of permissions granted by all assigned roles.

Unknown users and users without roles are denied interactive BossGate operations.

## Bootstrap Owner

On first registry creation, seed a local bootstrap owner:

```text
bossforge-owner
```

Assign `security_admin` to this owner. The bootstrap owner identity may later move to an installation or onboarding configuration workflow without changing the registry shape.

## Seeded Roles

### `viewer`

Permissions:

1. `bossgate.map.view`
2. `bossgate.discovery.run`
3. `agentforge.profile.view`

GUI:

1. BossGate Map
2. Discovery Map
3. Approved AgentForge profile views

### `operator`

Includes `viewer`.

Additional permissions:

1. `bossgate.package`
2. `bossgate.transfer`
3. `bossgate.install`

GUI:

1. BossGate operator controls for package, transfer, and install

### `security_admin`

Includes `operator`.

Additional permissions:

1. `bossgate.key.rotate`
2. `bossgate.roles.manage`

GUI:

1. Security role administration
2. Human-role assignment
3. Custom-role editor

Only users whose assigned roles include seeded `security_admin` may manage roles. Granting `bossgate.roles.manage` to a custom role does not grant role-management authority.

### `commerce_manager`

Includes `viewer`.

Additional permissions:

1. `bossgate.commerce.view`
2. `bossgate.license.issue`
3. `bossgate.license.validate`
4. `bossgate.usage.report`

GUI:

1. Commerce workspace
2. Clearly labeled pending license and usage command mechanisms

### `support_engineer`

Includes `viewer`.

Additional permissions:

1. `bossgate.support.view`
2. `bossgate.remote_debug.open`
3. `bossgate.remote_debug.close`

GUI:

1. Support workspace
2. Clearly labeled pending remote-debug session mechanisms

## Custom Roles

Seeded `security_admin` users may:

1. Create a custom role
2. Edit a custom role permission list
3. Assign one or more roles to a human user
4. Remove role assignments

Seeded roles are immutable through the custom-role editor.

Custom-role names must be non-empty lowercase identifiers using letters, numbers, underscores, and hyphens. Custom permissions must come from the known BossGate permission catalog.

## Shared Authorization Evaluator

Create a shared BossGate authorization module that:

1. Loads or creates the registry
2. Resolves effective roles
3. Resolves effective permissions
4. Checks whether a human user has a permission
5. Checks whether a user is a seeded `security_admin`
6. Creates or edits custom roles
7. Assigns roles to users
8. Returns GUI capability metadata

BossGate and Control Hall must call the same evaluator rather than maintain separate permission logic.

## Sensitive BossGate Actions

Human-triggered actions require `operator_id`, `scope_id`, and permission:

1. Discovery: `bossgate.discovery.run`
2. Scan: `bossgate.discovery.run`
3. Package: `bossgate.package`
4. Transfer: `bossgate.transfer`
5. Install: `bossgate.install`
6. Key rotation: `bossgate.key.rotate`

Passive beacon-map refresh remains internal read-only telemetry.

## Agent-Originated Actions

Agent-originated actions identify the actor with:

```text
actor_type=agent
```

Required agent skills:

1. Package: `bossgate_coms_officer`
2. Transfer: `bossgate_travel_control`
3. Install: `bossgate_coms_officer`
4. Future remote debug: `bossgate_remote_debug`

Agent profiles are loaded from the local model-profile registry. Missing agent profiles or missing required skills are denied.

Human-originated actions use:

```text
actor_type=human
```

For compatibility, omitted `actor_type` normalizes to `human`.

## Control Hall GUI

Add a BossGate Access workspace with:

1. Current-user selector
2. Effective roles
3. Effective permissions
4. Capability-driven navigation visibility
5. Operator package, transfer, and install controls
6. Security-admin role editor and assignments
7. Commerce workspace for commerce permissions
8. Support workspace for support permissions

The browser stores the selected user locally and sends it as `operator_id` for interactive BossGate actions.

GUI controls derive from effective permissions. Custom roles automatically receive matching interface mechanisms when granted catalog permissions.

## Error Handling

1. Unknown human user: deny with `authorization denied: unknown operator`.
2. Missing permission: deny with the required permission in the response.
3. Unknown agent: deny with `authorization denied: unknown agent`.
4. Missing skill: deny with the required skill in the response.
5. Invalid custom role: return a validation error without mutating the registry.
6. Non-security-admin role edits: deny without mutating the registry.

Explicit structured deny reason codes are deferred to `BG-012`; `BG-011` responses include clear human-readable messages.

## Test Coverage

Automated tests must verify:

1. Bootstrap registry creates `bossforge-owner` as seeded `security_admin`.
2. Multi-role assignments union permissions.
3. Only seeded `security_admin` users may create roles or assign users.
4. Custom roles reject unknown permissions.
5. GUI capability metadata reflects effective permissions.
6. Unknown humans are denied sensitive BossGate actions.
7. Human permissions gate package, transfer, install, and key rotation.
8. Agent skills gate package, transfer, and install.
9. Passive map snapshots remain readable.
10. Control Hall routes expose current-user capabilities and security-admin role-management forwarding.

## Documentation Updates

Update:

1. `docs/bossgate_connector.md`
2. `docs/bossgate_protocol.md`
3. `docs/bossgate_connector_todo.md`
4. `docs/AgentForge_readme.md`

Mark `BG-011` complete only after relevant automated suites pass.
