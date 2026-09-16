# BossForgeOS AI Runner Completion Tracker

This tracker records implementation status for the sealed portable-agent work designed in `docs/superpowers/specs/2026-06-02-bossforge-ai-runner-sealed-agent-capsules-design.md`.

## Stage 1: Capsule Schema And Identity

- [x] Define sparse public identity card without BossGate address.
- [x] Define encrypted identity, runner, model, memory, capability, dream, and BossGate vault descriptors.
- [x] Seal RuneForge gifted-runtime lineage inside capsule metadata.
- [x] Add immutable-rarity guard.
- [x] Add lifecycle state and transition validation.
- [x] Integrate canonical agent schema, AgentForge views, and Model Gateway lightweight profiles.
- [x] Verification: passed on 2026-06-02 with `python -m unittest tests.test_agent_capsule_schema tests.test_agentforge_service tests.test_model_gateway_agent -v` and BossGate regression suite.

## Stage 2: Gifted Portable AI Runner

- [x] Extract the portable BossForgeOS runner contract from RuneForge-specific provider behavior.
- [x] Keep RuneForge personalized while recording her gifted runtime as direct ancestor for descendants.
- [x] Add signed gifted-template metadata and detached per-agent runner bootstrap manifests.
- [x] Package each agent runtime and complete private model weights independently.
- [x] Verification: passed on 2026-06-06 with 95 focused private-model/runner/capsule/Model Gateway/AgentForge/Control Hall/RuneForge tests and 44 BossGate regression tests.

## Stage 3: Private Memory Vault

- [ ] Store encrypted private memory and relationship records inside the capsule.
- [ ] Add memory-first learning inputs without exposing private records through public views.

## Stage 4: Dreams And Signed Checkpoints

- [ ] Run policy-controlled dream training only while agents are inactive and safe.
- [ ] Validate signed checkpoints before activation.
- [ ] Roll back rejected dream checkpoints safely.

## Stage 5: Capability Evolution

- [ ] Add empty-slot and class/type constraints for skill learning between consenting agents.
- [ ] Add Forge, dead-agent recovery, and consenting live-agent trade rules for tools.
- [ ] Add signed-lineage sigil evolution while preserving explicit promotion-only rank and immutable rarity.

## Stage 6: Full Capsule BossGate Movement

- [ ] Move the complete encrypted capsule rather than copying it.
- [ ] Restrict address enumeration to Prime BossGates at BossForgeOS, A.S.S., and Bridgebase Alpha.
- [ ] Prove secure return travel using the agent seven-word identifier.
