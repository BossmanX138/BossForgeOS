# TODOs for BossForgeOS Enterprise Roadmap (Agent-Ready)

## Phase 1: Enterprise Core
- [ ] Design BossCrafts Protocol v1 message schemas (YAML/JSON schema files)
- [ ] Implement BossCrafts Protocol v1 versioning and compatibility checks
- [ ] Add structured event schemas to Rune Bus (define event types, schemas)
- [ ] Implement agent execution trace logging (per-agent, per-event)
- [ ] Add per-agent SLA/health scoring logic (daemon/agent health monitors)
- [ ] Define canonical OS state model (schema, serialization, diff)
- [ ] Implement time-travel state diff and restore
- [ ] Add audit-grade immutable logs (append-only, signed)
- [ ] Implement signed agent manifests (manifest schema, signing tool)

## Phase 2: Control Plane & UI
- [ ] Scaffold React/HTMX/Flask hybrid UI for Control Hall
- [ ] Build live dashboards (agent status, event streaming, analytics)
- [ ] Implement drag-and-drop agent wiring UI
- [ ] Add visual bus inspector (event/topic explorer)
- [ ] Build soundstage mixer UI (routing, EQ, diagnostics)
- [ ] Add model endpoint health dashboard (status, metrics)
- [ ] Implement runtime topology view (graph of daemons/agents)

## Phase 3: Agent/Daemon Evolution
- [ ] Refactor agents to subscribe/react to bus events (consumables)
- [ ] Implement agent telemetry emission (structured logs, metrics)
- [ ] Add capability-scoped lease system (token/lease manager)
- [ ] Implement per-agent sandboxing (resource limits, isolation)
- [ ] Add config overlays and daemon orchestration profiles (profile loader)

## Phase 4: Developer Experience
- [ ] Implement ForgeShell REPL (command parser, bus/event integration)
- [ ] Add autocompletion and inline bus event streaming
- [ ] Build state tree viewer and agent log inspector
- [ ] Implement ritual recording/playback (ritual engine)
- [ ] Add developer hot-reload for agents/daemons
- [ ] Integrate time-travel debugging tools

## Phase 5: Mythic Layer
- [ ] Layer mythic identity (voice monikers, ritual commands, persona-driven UX)
- [ ] Add narrative-driven onboarding and persona prompts
- [ ] Integrate soundstage sensory identity into UI/UX

---
Each TODO is staged for agent delegation. Agents can be assigned to design, implement, test, or document each item as discrete tasks.
