# BossGate Operator Runbook

## Purpose

This runbook is the operator guide for BossGate package, transfer, install, licensing, remote debug, and connector-synthesis workflows in BossForgeOS.

Use it when you need to:

1. Validate an approved transfer target
2. Package or install an agent
3. Rotate BossGate keys safely
4. Open or revoke remote debug sessions
5. Generate connector artifacts for approved targets
6. Roll back a recent BossGate operator action

## Preconditions

Before running any BossGate mutation:

1. Confirm you have a valid `operator_id`
2. Confirm you have a scoped `scope_id` for the task or incident
3. Confirm the target is an approved BossGate-compatible system
4. Confirm you are operating from a super gate before initiating travel

Operator-triggered BossGate commands are denied unless both `operator_id` and `scope_id` are provided.

## Common State Files

BossGate state is stored under `bus/state/`.

Key files:

1. `bus/state/bossgate_keys.json`
2. `bus/state/bossgate_replay_tokens.json`
3. `bus/state/bossgate_map.json`
4. `bus/state/bossgate_remote_debug_sessions.json`
5. `bus/state/bossgate_remote_debug_transcripts.jsonl`
6. `bus/state/bossgate_interface_maps/`
7. `bus/state/bossgate_connector_skeletons/`
8. `bus/state/bossgate_connector_pending_approval.json`
9. `bus/state/bossgate_licenses/`
10. `bus/state/bossgate_packages/`

## Preflight Checklist

Run these checks before packaging, transferring, or installing:

1. `bforge bossgate discover --timeout 3 --operator-id <id> --scope-id <scope>`
2. `bforge bossgate scan <destination> --operator-id <id> --scope-id <scope>`
3. `bforge bossgate map --refresh --timeout 2`

Expected results:

1. Discovery returns approved gates or agents
2. Scan reports `allowed_for_transfer: true`
3. Map refresh shows the target in `travelable_gates` when appropriate

## Core Operations

### Package an Agent

Use:

```text
bforge bossgate package <agent_name> --target-system-id <id> --operator-id <id> --scope-id <scope>
```

Optional flags:

1. `--secret-key`
2. `--output-file`
3. `--policy-ref`
4. `--visibility-profile`

Success result:

1. A package file is written under `bus/state/bossgate_packages/` unless an explicit output path is provided
2. The package contains an encrypted envelope and package metadata wrapper

### Validate or Transfer a Package

Dry run:

```text
bforge bossgate transfer <package_file> <destination> --dry-run --operator-id <id> --scope-id <scope>
```

Live transfer:

```text
bforge bossgate transfer <package_file> <destination> --no-dry-run --operator-id <id> --scope-id <scope>
```

Use `--resume-from-chunk <N>` only for a previously interrupted live transfer.

### Install a Package

Use:

```text
bforge bossgate install <package_file> --operator-id <id> --scope-id <scope>
```

If the package was sealed with a non-default key, provide `--secret-key`.

### Rotate Keys

Use:

```text
bforge bossgate rotate-key --key-id <new-id> --secret-key <new-secret> --operator-id <id> --scope-id <scope>
```

Expected behavior:

1. The new key becomes `active_key_id`
2. Older keys remain available for validating already-issued packages

### Issue, Validate, or Revoke Licenses

Use:

```text
bforge bossgate license-issue <agent_name> --customer-id <customer> --operator-id <id> --scope-id <scope>
bforge bossgate license-validate <license_file> --agent-name <agent_name> --operator-id <id> --scope-id <scope>
bforge bossgate license-revoke <license_file> --reason <text> --operator-id <id> --scope-id <scope>
```

## Remote Debug Operations

### Open a Session

Use:

```text
bforge bossgate remote-debug-open <agent_name> --session-scope logs.read state.inspect --operator-id <id> --scope-id <scope>
```

Effects:

1. Session metadata is written to `bossgate_remote_debug_sessions.json`
2. Audit entries are appended to `bossgate_remote_debug_transcripts.jsonl`

### Close or Revoke a Session

Close one session:

```text
bforge bossgate remote-debug-close --session-id <session_id> --operator-id <id> --scope-id <scope>
```

Emergency revoke for an agent:

```text
bforge bossgate remote-debug-close --agent-name <agent_name> --emergency-revoke --operator-id <id> --scope-id <scope>
```

Use emergency revoke when:

1. Scope drift is suspected
2. Operator credentials are in doubt
3. Incident containment is more important than preserving the session

## Connector Synthesis Operations

### Build an Interface Map

Current bus command:

1. `bossgate_build_interface_map`

The result is persisted under `bus/state/bossgate_interface_maps/`.

### Generate a Least-Privilege Connector Skeleton

Current bus command:

1. `bossgate_generate_connector_skeleton`

The result is persisted under `bus/state/bossgate_connector_skeletons/`.

Skeleton behavior:

1. Read-only endpoints such as `GET`, `HEAD`, or `OPTIONS` are enabled by default
2. Write or destructive endpoints remain under `approval_required_operations`
3. Approved targets only

### Enable a Gated Connector Operation

Current bus command:

1. `bossgate_enable_connector_operation`

This does not enable the operation immediately. It creates a pending approval record in:

1. `bus/state/bossgate_connector_pending_approval.json`

Approval response command:

1. `bossgate_respond_connector_operation_approval`

## Rollback Steps

### Roll Back a Key Rotation

BossGate keeps old keys, so rollback is usually “rotate back” rather than restore from backup.

Steps:

1. Open `bus/state/bossgate_keys.json`
2. Identify the previous working key id and secret
3. Run `bforge bossgate rotate-key --key-id <previous-id> --secret-key <previous-secret> --operator-id <id> --scope-id <scope>`
4. Re-run a known-good package install validation

### Roll Back a Failed Package Transfer

If the transfer was dry-run only:

1. No rollback is required

If the transfer was live and interrupted:

1. Re-run with `--resume-from-chunk <N>` when recovery is intended
2. If the target should not receive the package, revoke any related license and rotate keys if compromise is suspected
3. Generate a fresh package if replay state was consumed

### Roll Back an Install Validation Attempt

Validation does not mutate the installed runtime, but replay protection is consumed on success.

Steps:

1. Do not reuse the same successfully validated package file
2. Re-package the agent to produce a fresh envelope
3. Re-run install validation with the new package

### Roll Back a Remote Debug Session

Steps:

1. Close the session with `remote-debug-close`
2. If multiple sessions exist or trust is reduced, use `--emergency-revoke`
3. Verify transcript entries were appended in `bossgate_remote_debug_transcripts.jsonl`

### Roll Back an Approved Connector Write Operation

Current limitation:

1. BossGate has an approval-enable flow, but no dedicated disable command yet

Manual rollback steps:

1. Open the skeleton file under `bus/state/bossgate_connector_skeletons/`
2. Locate the operation in `approval_required_operations`
3. Set `enabled` to `false`
4. Set `approval_required` to `true`
5. Preserve the previous `approved_by` and `approved_at` fields for audit history, or move them into a local operator note
6. Record the manual rollback in the incident log

## Failure Triage

If a command fails:

1. Check the returned `reason_codes`
2. Verify `operator_id` and `scope_id`
3. Verify the target is approved for transfer
4. Verify the package file still exists and has not already consumed replay state
5. Verify the required secret key matches the package or license material

Common failure categories:

1. `missing_authorization_context`
2. `missing_permission`
3. `target_not_approved_for_transfer`
4. `envelope_validation_failed`
5. `payload_decryption_failed`
6. `license_revoked`
7. `license_expired`
8. `remote_debug_scope_denied`
9. `remote_debug_session_expired`

## Post-Change Verification

After any non-trivial BossGate operator action:

1. Re-run the relevant `discover`, `scan`, or `map` command
2. Verify the resulting state file changed as expected
3. For remote debug, inspect the latest transcript entries
4. For connector synthesis, inspect the generated interface map or skeleton file
5. For key changes, validate one known-good legacy package and one newly issued package
