# BossGate Features — Master TODO List

## Prime BossGate Tab
- [ ] Design and implement Prime BossGate UI (messenger, file transfer, voice chat, address book, status)
- [ ] Integrate address ledger and presence/status indicators
- [ ] Skill/role-gate all features

## Encrypted Messenger
- [ ] Implement TLS 1.3+ mutual authentication for all encrypted comms
- [ ] Support for multi-agent and human chat
- [ ] Message history, search, and audit logs

## File Transfer
- [ ] Secure file transfer protocol (chunked, resumable, encrypted)
- [ ] UI for sending/receiving files
- [ ] Audit and access controls

## Voice Chat
- [ ] Integrate WebRTC or secure VoIP for encrypted voice
- [ ] UI for call controls (start, mute, end)
- [ ] Presence/status integration

## Address Ledger
- [ ] Encrypted ledger storage (AES-256-GCM)
- [ ] Tamper-evidence (HMAC/digital signatures)
- [ ] Privacy boundaries for foreign addresses
- [ ] Master ledger for Prime BossGates

## Secure Address Format
- [ ] Enforce 7-word, asterisk-wrapped address format
- [ ] Cryptographically secure address generation

## Skill/Role Gating
- [ ] Implement skill checks for agents, role checks for humans
- [ ] Map roles to permissions for all features

## Credential Management
- [ ] USB BossGate Key: creation, reading, access enforcement
- [ ] NFC/RF credential: encoding, scanning, access enforcement
- [ ] Authenticator app (TOTP/HOTP): setup, verification
- [ ] Multi-factor support
- [ ] Admin/admiral/general agent issuance workflow
- [ ] Request terminal workflow with alternate verification
- [ ] Credential rotation, revocation, and audit logs

## Security
- [ ] Integrate with secure key vault for key management
- [ ] Secure deletion of credentials/ledgers
- [ ] All comms and ledgers encrypted at rest and in transit

## Extensibility
- [ ] Video chat, group chat, collaborative editing, etc.
- [ ] Hardware token (YubiKey) and biometric support

---
All features must be skill/role-gated, logged, and privacy-compliant.

---
## TODO List Cross-References & Archivist Duties

This master TODO is the canonical BossGate feature tracker. All other TODO lists and tracked work items must be referenced here and kept in sync by the Archivist agent.

### Linked TODO Lists (must be kept accurate and up to date):

- [BossForgeOS Enterprise TODO List](../../ENTERPRISE_TODO_LIST.md)
- [BossForgeOS Enterprise Roadmap](../../ENTERPRISE_ROADMAP.md)
- [Global TODO/Backlog/Curated List](../../docs/todos.md)
- [BossGate Protocol/Connector Docs](../../docs/bossgate_protocol.md), [bossgate_connector.md](../../docs/bossgate_connector.md)

### Archivist Duties

- Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.
- Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.
- For each area (BossGate, Enterprise, Mythic Layer, etc.), ensure TODOs reflect actual outstanding work and are delegated to agents as needed.
- When a TODO is completed, update all lists and remove or archive the item.
- If a TODO is moved, merged, or split, update all references and cross-links.

---
The Archivist is responsible for TODO list hygiene and cross-repo accuracy.
