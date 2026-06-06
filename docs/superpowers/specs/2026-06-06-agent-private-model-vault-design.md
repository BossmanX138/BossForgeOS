# Agent Private Model Vault Design

Date: 2026-06-06
Status: Approved design for BossForgeOS AI Runner Stage 2

## Goal

Complete Stage 2 of the BossForgeOS AI Runner by giving every forged
LLM-enabled agent its own complete, encrypted, independently owned model
package at creation time.

A completed agent is always portable and self-contained. The Forge source
model is protected creation material, not a non-portable version of the
agent. RuneForge's personalized model and runner remain uniquely hers, while
descendants receive independent packages created from an approved source.

## Governing Decisions

1. AgentForge packages the model immediately during agent creation.
2. Agent creation does not succeed until the package is complete, encrypted,
   verified, and bound to the agent capsule.
3. Model files are streamed into authenticated encrypted chunks rather than
   loaded into memory or placed in one monolithic archive.
4. Each package belongs to exactly one agent.
5. Sibling agents must not share package directories, encryption identities,
   encrypted chunks, or active model paths.
6. The Forge source remains unchanged after successful packaging.
7. BossGate later transports this exact agent-owned package with the complete
   capsule.

## Scope

This stage implements:

1. Source model discovery and validation.
2. Complete file inventory and categorization.
3. Per-agent encrypted chunk packaging.
4. Package and file integrity manifests.
5. Atomic staging, verification, and activation.
6. Runner and capsule model-vault binding.
7. AgentForge creation integration.
8. Package verification and isolation tests.
9. Documentation and completion-tracker updates.

This stage does not implement:

1. BossGate network transport or source retirement.
2. Destination installation and wake.
3. Dream training or post-dream checkpoint creation.
4. Production key-management infrastructure.
5. Runtime decryption or protected model mounting beyond the package contract
   needed by a later loader stage.

## Package Contents

The private model package inventories and encrypts the complete source model
tree. Its manifest categorizes at least:

1. Model weights, including sharded weight indexes and shards.
2. Tokenizer files and vocabulary assets.
3. Model configuration.
4. Generation configuration.
5. Adapter configuration and adapter weights when the selected source uses an
   adapter.
6. Runtime requirements needed to load the model.
7. Training and source provenance available at forging time.
8. Checkpoint metadata.

Files not recognized as one of these categories remain part of the package as
supporting model assets. Packaging must not silently discard unknown files
from an approved source tree.

An adapter-only source is incomplete by itself. AgentForge must resolve and
package both the adapter and its complete base model so the agent does not
depend on a Forge-side or network-accessible base model after creation.

## Architecture

### Private Model Vault Service

A focused core service owns package construction and verification. It exposes
interfaces for:

1. Inspecting and validating a source model directory.
2. Building a package for one normalized agent ID.
3. Verifying an existing package against its manifest.
4. Producing the sealed model-vault binding used by the capsule and runner.

The service contains no AgentForge UI logic and no BossGate transport logic.

### Source Inspector

The source inspector:

1. Resolves the source root to an absolute path.
2. Rejects missing directories, links escaping the source root, path
   traversal, unreadable files, and empty files where the format requires
   content.
3. Requires model configuration and tokenizer assets.
4. Requires either complete model weights or a complete adapter plus resolved
   base model.
5. Detects sharded indexes and verifies that every declared shard exists.
6. Produces a deterministic relative-path inventory.

### Encrypted Chunk Writer

Each source file is read in bounded binary chunks. Every chunk is encrypted
independently using AES-256-GCM with:

1. A fresh random nonce.
2. A package-specific key resolved through a protected key reference.
3. Authenticated associated data containing the package ID, agent ID, relative
   path, chunk index, and plaintext size.
4. A plaintext SHA-256 digest for verification after authorized decryption.
5. A ciphertext SHA-256 digest for storage and transport integrity checks.

Raw encryption keys are never written to the package manifest, capsule,
runner manifest, logs, profile views, or documentation. Stage 2 accepts a key
provider interface and records only a non-secret key reference. Production
key custody remains a later security-infrastructure responsibility.

### Package Layout

The active package root uses an agent-owned location outside public profile
data:

```text
<private-model-root>/
`-- <agent-id>/
    `-- <package-id>/
        |-- package.manifest.enc
        |-- package.attestation.json
        `-- chunks/
            `-- <file-id>/
                |-- 000000.chunk
                |-- 000001.chunk
                `-- ...
```

The encrypted manifest contains proprietary source paths, filenames,
provenance, categories, and plaintext hashes. The non-secret attestation
contains only the package ID, normalized owner ID, schema version, encryption
algorithm, encrypted-manifest digest, aggregate ciphertext digest, creation
timestamp, key reference, and verification status.

The attestation must not contain a BossGate address, model source path, model
name, tokenizer details, ancestry, or raw file inventory.

### Package Manifest

The sealed manifest records:

1. Schema version and package ID.
2. Normalized owner agent ID.
3. Creation timestamp.
4. Source provenance.
5. Encryption algorithm and key reference.
6. Total plaintext and ciphertext sizes.
7. Deterministic file inventory.
8. Category assignments.
9. Per-file and per-chunk sizes and hashes.
10. Adapter-to-base-model resolution when applicable.
11. Runtime requirement metadata.
12. Genesis checkpoint attestation.
13. Runner contract and gifted-template versions.

The genesis checkpoint signs or attests the newly forged model package as the
agent's initial rollback baseline. It references the same agent-owned
encrypted chunks rather than storing a second duplicate of the initial
weights. Later dream stages may add independent encrypted checkpoint weight
sets within this same agent's vault.

## Creation Data Flow

1. AgentForge validates the requested agent profile and source model
   selection.
2. The source inspector builds and validates the complete source inventory.
3. AgentForge obtains a unique package ID and protected per-agent key
   reference.
4. The vault service creates a staging directory beneath the intended
   private-model root.
5. Source files are read in bounded chunks, encrypted, hashed, and written to
   staging.
6. The encrypted package manifest and non-secret attestation are written.
7. The service decrypts and verifies every staged chunk against the sealed
   manifest.
8. The service verifies file reconstruction hashes, required categories,
   package ownership, and aggregate attestation.
9. The staging directory is atomically renamed to its final package path.
10. The capsule model vault receives the package ciphertext reference.
11. The agent runner manifest receives the private model package binding.
12. Agent creation completes only after the final capsule and runner
    validations pass.

## Atomicity And Failure Handling

Packaging is fail-closed:

1. A partial package is never activated.
2. Existing packages are never overwritten in place.
3. A collision on agent ID or package ID fails creation.
4. Insufficient disk space fails before encryption begins when a reliable
   preflight estimate can be made.
5. Read, write, encryption, verification, or rename failures remove only the
   staging directory created by the current operation.
6. The Forge source is never deleted or modified.
7. Agent profile publication and success events occur only after package
   activation and binding.
8. Logs expose package IDs and error categories but not keys, source paths,
   filenames, plaintext hashes, or decrypted metadata.

If cleanup cannot remove a staging directory, it is marked quarantined and
must never be treated as an active package.

## Ownership And Isolation Rules

Validation rejects:

1. A manifest owner that does not match the capsule and runner agent ID.
2. A package path located beneath another agent's package directory.
3. Two agents referencing the same active package ID.
4. Two agents referencing the same active package directory.
5. Hard links, junctions, symbolic links, or other aliases that cause package
   files to resolve into another agent's vault.
6. A package key reference already registered as another agent's private model
   key when the key provider declares it agent-exclusive.
7. Runtime paths that point back to the Forge source model.
8. Adapter packages that retain an external base-model dependency.

Physical filesystem deduplication and copy-on-write clones are not used by
the package builder. Each agent receives newly encrypted ciphertext, fresh
nonces, and an independently owned package.

## Runner And Capsule Binding

The existing runner bootstrap model-vault binding is extended with a sealed
private model package descriptor containing:

1. Package schema version.
2. Package ID.
3. Owner agent ID.
4. Package ciphertext reference.
5. Attestation digest.
6. Key reference.
7. Verification state.

The capsule `model` vault descriptor points to the active encrypted package.
Hidden and non-hidden profile views never expose the descriptor's proprietary
manifest contents, model files, source details, or keys.

The binding validator confirms that capsule, runner, package attestation, and
sealed manifest all identify the same agent and package.

## Security Boundary

1. Model plaintext exists only at the approved Forge source and transiently
   inside bounded encryption or authorized verification buffers.
2. Staging and active package storage contain encrypted chunks only.
3. AES-GCM authentication detects ciphertext or associated-data tampering.
4. SHA-256 inventories detect missing, reordered, truncated, or substituted
   chunks and files.
5. Relative paths are canonicalized before use.
6. Package extraction is not part of ordinary profile access.
7. Key resolution is an injected privileged operation.
8. Package verification does not make the package public or reusable by
   another agent.

## Testing Strategy

Tests must prove:

1. A complete model source creates a verified encrypted package.
2. Plaintext model bytes and proprietary filenames do not appear in active
   chunk files or the public attestation.
3. Large files are processed through bounded streaming reads.
4. Missing configuration, tokenizer files, weights, indexes, or declared
   shards fail creation.
5. Adapter-only sources package their resolved complete base model.
6. Unresolved adapter base models fail creation.
7. Unknown supporting files remain represented in the inventory.
8. Tampered ciphertext, nonce metadata, hashes, ownership, or associated data
   fails verification.
9. Interrupted creation leaves no active package.
10. Failed packaging prevents agent creation and profile publication.
11. Path traversal and source-root escapes are rejected.
12. Sibling agents built from the same Forge source receive distinct package
    IDs, directories, nonces, ciphertext, and ownership bindings.
13. A sibling package cannot be rebound to another capsule or runner.
14. The final runtime binding does not reference the Forge source.
15. The Forge source remains byte-for-byte unchanged.
16. Existing runner, capsule, AgentForge, Model Gateway, and BossGate
    regression suites continue to pass.

## Documentation Updates

Implementation updates:

1. `docs/bossforge_ai_runner_todo.md`
2. `docs/AgentForge_readme.md`
3. `docs/agentforge_requirements.md`
4. `docs/agentmaker_requirements.md`
5. `docs/agents_bossgate_agentforge_schema_guide.txt`
6. `docs/bossgate_connector.md` where the future full-capsule package boundary
   is described
7. `docs/bossgate_protocol.md` where the future travel payload is described

The Stage 2 tracker item is marked complete only after the private model
package implementation and its regression suites pass.

