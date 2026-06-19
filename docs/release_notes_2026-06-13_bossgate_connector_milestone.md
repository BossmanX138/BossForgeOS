# Release Notes: BossGate Connector Milestone

Date: `2026-06-13`

## Summary

This milestone completes the current BossGate connector implementation arc across transfer telemetry, licensing, remote debug controls, connector synthesis, and initial hardening.

The BossGate surface now supports:

1. Role- and scope-aware operator authorization
2. Auditable package, transfer, install, and usage-report flows
3. License issue, validate, and revoke operations
4. Remote debug open, close, emergency revoke, and scope validation
5. Interface-map generation for approved targets
6. Least-privilege connector skeleton generation
7. Explicit approval gating for write or destructive connector operations
8. Migration coverage for legacy keyring and package shapes
9. Fuzz coverage for malformed envelope and payload inputs

## Operator-Facing Additions

Major operator-visible capabilities added in this milestone:

1. `bossgate_usage_report`
2. `bossgate_license_issue`
3. `bossgate_license_validate`
4. `bossgate_license_revoke`
5. `bossgate_remote_debug_open`
6. `bossgate_remote_debug_close`
7. `bossgate_remote_debug`
8. `bossgate_build_interface_map`
9. `bossgate_generate_connector_skeleton`
10. `bossgate_enable_connector_operation`
11. `bossgate_respond_connector_operation_approval`

Primary operator reference:

1. `docs/bossgate_operator_runbook.md`

## Security and Safety Notes

Important safety properties now enforced:

1. Operator-triggered actions require `operator_id` and `scope_id`
2. Sensitive operations are permission-gated
3. Transfer targets are allowlisted
4. Package installation is replay-protected
5. License revocation and expiry block install/runtime activation
6. Remote debug sessions are time-bound, scoped, and auditable
7. Connector write operations require explicit post-generation approval

## Migration and Compatibility Notes

This milestone includes compatibility behavior for older local artifacts:

1. Legacy flat keyrings are migrated into the current `{active_key_id, keys}` structure
2. Legacy package files that store the raw envelope at top level are still installable
3. Legacy transfer packages without a resume plan remain transferable
4. Legacy envelopes without a chunk manifest remain valid

## Known Limitations

Current gaps to track after this milestone:

1. Connector write-operation rollback is still manual; there is no dedicated disable command yet
2. The CLI does not yet expose every newer BossGate bus command directly
3. Acceptance remains local-test based; there is no external deployment signoff recorded in this artifact

## Verification Snapshot

Latest full verification used for this milestone:

```text
python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v
python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q
```

Observed result:

1. `117` tests passed
2. `0` failures
3. `0` resource warnings promoted to errors

## Acceptance Checklist

Mark each item before calling the BossGate connector milestone release-ready.

- [x] Operator authorization is required for sensitive BossGate actions
- [x] Transfer validation denies non-approved targets
- [x] Package install validates signed encrypted envelopes
- [x] Replay-protection checks reject reused envelopes
- [x] Transfer ledger and usage reporting are auditable
- [x] License issue, validate, and revoke flows are covered
- [x] Remote debug open, close, revoke, and denial paths are covered
- [x] Connector interface-map generation is covered
- [x] Least-privilege connector skeleton generation is covered
- [x] Connector write operations require explicit approval
- [x] Legacy keyring and legacy package migration paths are covered
- [x] Malformed envelope and payload fuzz cases reject cleanly
- [x] Operator runbook and rollback guidance are published
- [ ] External operator signoff completed
- [ ] Production-target dry run completed outside the unit-test harness
