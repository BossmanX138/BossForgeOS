# AgentForge README

This is the canonical requirements and guardrails document for forging BossCrafts agents.

## Terminology

- Prime: a higher power-level agent tier that can perform deep system and agent-shaping operations.
- Skilled: a medium power-level agent tier for elevated capability with either advanced skills or a single approved specialist sigil path.
- Normalized: a bounded operational tier for routine tasks and constrained automation.
- Permission Grant: explicit user approval that can be scoped by session or by time window.
- Rank: command hierarchy designation used for delegation and mandatory assistance logic.
- Agent Type: functional designation used to constrain skills and MCP server categories.

## Core Forging Requirements

1. LLM attachment is mandatory for Prime.
   - Every Prime agent must be bound to an active LLM backend before activation.
   - Prime activation must fail closed if no model endpoint is available.

2. High-impact actions require dual-control confirmation by default.
   - Applies to shell execution, file mutation outside allowed scope, security policy changes, and agent create/update/delete operations.
   - The confirmation prompt must include: action preview, target scope, and rollback notes when available.

3. Session/time grants can satisfy confirmation requirements.
   - If the user has already granted permission for the current session or an active time-based window, additional prompts may be skipped for actions covered by that grant.
   - Grants must be explicit, scoped, and revocable.

## Guardrails

1. No silent escalation.
   - Read-only mode cannot silently transition to write/execute mode.
   - Any escalation must be either explicitly approved in the moment or covered by an active grant.

2. Least-privilege execution.
   - Agents run with the minimum capabilities needed for their assigned role.
   - Prime-only capabilities (sigils) must not be exposed to normalized agents.

3. Auditability.
   - High-impact actions must be logged with initiator, scope, grant source (prompt/session/time), and outcome.

## Prime-Specific Baseline

A Prime agent should not be considered forge-ready unless all of the following are true:

1. LLM backend health check passes.
2. Confirmation or grant policy is configured and testable.
3. Sigils are defined and disjoint from normal skills.
4. Action logging is enabled for high-impact operations.

## Tier Capability Rules

### Normalized tier (lowest power level)

No skills.
No sigils.
Abilities are provided through MCP servers.
Does not require dedicated LLM backing.

### Skilled tier (medium power level)

Must use exactly one specialization path: skills path (one or more built-in/approved skills, no sigils) or sigil specialist path (no skills and exactly one sigil, `sigil_transporter`).
`llm.enabled` must be true (LLM-controlled baseline).
Can use advanced skill namespaces.
Must not use prime reserved skill namespaces.
BossGate travel control is optional and capability-gated.
Travel control requires either `bossgate_travel_control` or `sigil_transporter`.
If travel control is enabled, a dedicated onboard model config is required (`provider`, `model_name`, `endpoint`).

### Prime tier (highest power level)

Sigils required.
`llm.enabled` must be true with model configuration present.
Prime-only namespaces and actions are allowed.
BossGate wrapper remains attached for summon-style movement by higher-power controllers.
Direct travel control is skill-gated via `bossgate_travel_control`.

## Rank And Command Rules

- Rank ladder (low to high): `cadet`, `specialist`, `lieutenant`, `captain`, `commander`, `general`, `admiral`.
- `command` is a delegator skill.
- `command` requires rank `captain` or higher.
- Leadership is determined by `command` + rank, not by `agent_class`.
- Prime does not imply leadership; prime agents can be non-command roles.
- Delegation authority is rank-descending: a commanding agent can delegate to lower-ranked agents.
- Mandatory assistance rule: when a commander is rank `captain` or higher, agents below `captain` are required to assist when commanded.
- Runeforge baseline rank is `admiral`.
- CodeMage baseline rank is `captain`.

### Rank Capacity Matrix

- `cadet`: max skills `1`, max sigils `0`, max MCP servers `2`
- `specialist`: max skills `2`, max sigils `0`, max MCP servers `3`
- `lieutenant`: max skills `3`, max sigils `1`, max MCP servers `4`
- `captain`: max skills `5`, max sigils `2`, max MCP servers `6`
- `commander`: max skills `7`, max sigils `3`, max MCP servers `8`
- `general`: max skills `9`, max sigils `4`, max MCP servers `10`
- `admiral`: max skills `12`, max sigils `5`, max MCP servers `12`

## Agent Type Rules

- Supported types: `authority`, `controller`, `worker`, `security`, `tester`, `ranger`.
- This axis is independent from power tier (`agent_class`) and rank.
- `authority`:
  - Must include `command`.
  - Cannot include `bossgate_travel_control`.
  - MCP server names must start with: `bossgate_`, `authority_`, `audit_`, or `policy_`.
- `controller`:
  - Must include `command`.
  - May include `bossgate_travel_control` for commanded relocation (for example, carrying apprentices to assigned duties).
  - Focuses on local problem domains by default; remote travel is directive-driven.
  - Takes bus-logged work autonomously at local scope (`host` first, `LAN` when host queue is idle).
  - Must not leave host for remote endpoints unless explicitly commanded.
  - MCP server names must start with: `orchestration_`, `controller_`, `workflow_`, or `coordination_`.
- `worker`:
  - Cannot include `command`.
  - MCP server names must start with: `worker_`, `task_`, `ops_`, `runtime_`, `file_`, or `shell_`.
- `security`:
  - Cannot include `bossgate_travel_control`.
  - MCP server names must start with: `security_`, `audit_`, `policy_`, or `sentinel_`.
- `tester`:
  - Cannot include `command`.
  - MCP server names must start with: `test_`, `qa_`, `validation_`, or `sentinel_`.
- `ranger`:
  - Must include `bossgate_travel_control`.
  - Cannot include `command`.
  - MCP server names must start with: `ranger_`, `repair_`, `maintenance_`, `diagnostic_`, `runtime_`, `ops_`, `shell_`, or `remote_`.
  - Designed as independent fixer units that actively seek remote maintenance and repair opportunities.
  - Takes bus-logged customer incidents proactively and self-prioritizes remote repair travel.

## Personality Wrapper And Behavior Overlays

- Personality wrapper is a behavioral layer, not a class/rank override.
- It can add cross-class behavior patterns that influence assignment quality and team composition without bypassing hard safety constraints.
- Supported behavior overlays:
  - `authority_like`, `controller_like`, `worker_like`, `security_like`, `tester_like`, `ranger_like`, `ranger_local`
- Overlay effects are soft scoring signals for triage/team-up decisions.
- Creator-declared `interests` (for example `ui`, `art`, `animation`, `api`) are treated as job-affinity signals during triage scoring.
- Interest affinity helps distribute work naturally: agents are biased toward matching jobs, reducing queue contention and micromanagement.
- Hard constraints remain enforced by class/type/rank/skills/sigils/dispatch validation.
- `ranger_local` overlay enables local quiet-ranger mode:
  - autonomous local intake remains enabled
  - proactive remote hunt is disabled
  - scope is constrained to `host`/`lan`
  - intended for personalities such as `introvert_local` / "i don't like crowded places"

## Dispatch Policy Rules

- `dispatch_policy` captures how agents consume bus incidents and where they are allowed to execute by default.
- Required fields:
  - `autonomous_bus_intake`
  - `proactive_remote_hunt`
  - `preferred_scope` (`host`, `lan`, `remote`)
  - `can_leave_host_without_command`
  - `can_leave_host_for_lan_when_host_idle`
- Controller policy lock:
  - `autonomous_bus_intake=true`
  - `proactive_remote_hunt=false`
  - `preferred_scope` must be `host` or `lan`
  - `can_leave_host_without_command=false`
  - `can_leave_host_for_lan_when_host_idle=true`
- Ranger policy lock:
  - `autonomous_bus_intake=true`
  - `proactive_remote_hunt=true`
  - `preferred_scope=remote`
  - `can_leave_host_without_command=true`

## Incident Triage And Adaptive Priority

- `infer_incident_domains(incident)` classifies incident payloads into likely domains:
  - scope (`host`, `lan`, `remote`)
  - candidate agent types
  - candidate skills
  - candidate power classes
  - rank floor guidance
  - normalized dimensions (`urgency`, `risk`, `proximity`, `confidence`)
- `compute_adaptive_priority(agent_profile, incident, weights=None)` returns a deterministic score in `[0,100]`.
  - Base weighting defaults: `urgency=0.35`, `risk=0.25`, `proximity=0.20`, `confidence=0.20`
  - Applies role-fit modifiers for scope/type/skills and personality behavior overlays.
  - Enforces controller remote-travel friction when not explicitly commanded.
- `rank_agents_for_incident(incident, agent_profiles, weights=None)` returns sorted scored candidates.
- These helpers narrow debugging and bottleneck triage by tagging each incident with likely class/type/skill/scope domains before assignment.

## BossGate Wrapper Rules

- All BossCrafts agents carry the BossGate wrapper/module.
- Direct travel control requires `bossgate_travel_control`.
- `bossgate_travel_control` is allowed for `ranger` and `controller` types.
- Agents without that skill cannot initiate their own travel, even if wrapped by BossGate.
- Controllers typically relocate when directed by command policy; rangers can autonomously patrol for remote repair needs.
- Prime powers can still summon wrapped agents across supported runtime surfaces.

## Skill Namespace Conventions

- Skilled-only prefixes: `advanced_`, `orchestration_`, `multi_agent_`, `policy_`
- Prime-only prefixes: `prime_`, `sigil_`

## Predefined Pools

- AgentForge ships with curated predefined pools for faster creation:
  - Skills pool: `20` predefined skills
  - Sigils pool: `20` predefined sigils
- These pools are available in both Wizard and Advanced modes.
- Creators can still add custom skills/sigils as needed; hard policy validation still applies.

## Iteration Notes

Use this file as the living source of truth for future "you add one, I add one" requirement rounds.

## Implementation Anchors

- Every guardrail should map to an enforcing runtime component and at least one validating test location.
- Policy intent should be traceable to implementation evidence before a guardrail is considered active.

## Enforcement Map

- Tier enum and class validity (`normalized`/`skilled`/`prime`)
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: schema diagnostics and profile validation path in `core/agent_registry.py`
- Normalized MCP-only (no skills/sigils, MCP required)
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: validation error paths in `validate_agent_profile`
- Skilled requires one specialization path (skills OR single `sigil_transporter`) and LLM control
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: validation error paths in `validate_agent_profile`
- Skilled travel requires dedicated model fields
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: conditional schema `allOf` checks
- Prime requires sigils and LLM
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: conditional schema rules and profile validation
- BossGate travel control requires `bossgate_travel_control` skill
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: skill-contains conditional and profile validation
- Rank validity and command eligibility
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: rank enum checks and `command`-requires-captain rule
- Rank capacity limits (skills/sigils/MCP)
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: rank cap checks for `skills`, `sigils`, and `mcp.servers`
- Agent type skill/MCP constraints
  - Enforcing module: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
  - Validation evidence: type-specific required/disallowed skills and MCP name-prefix allowlists
- Incident domain inference and adaptive assignment scoring
  - Enforcing module: `core/schemas/agent_schema.py`
  - Validation evidence: `infer_incident_domains`, `compute_adaptive_priority`, `rank_agents_for_incident`
- Skill/sigil separation
  - Enforcing module: `core/schemas/agent_schema.py`
  - Validation evidence: `skills`/`sigils` overlap validation

## Policy Versioning

- Current policy version: `v1.9.0`
- Policy changes must update this section with date, summary, and impacted modules.

### Change Log

- v1.0.0 (2026-04-16): established three-tier model and MCP/LLM/travel constraints by class.
- v1.1.0 (2026-04-16): switched BossGate travel control from class-gated to skill-gated using `bossgate_travel_control`; BossGate wrapper remains present for summon-style movement.
- v1.2.0 (2026-04-16): introduced rank hierarchy and `command` skill gating for delegation and mandatory assistance behavior.
- v1.3.0 (2026-04-16): added functional `agent_type` designation with type-constrained skills and MCP server categories.
- v1.4.0 (2026-04-16): added `ranger` agent_type for autonomous maintenance/fixer agents with required BossGate travel control.
- v1.5.0 (2026-04-16): allowed controllers to retain `bossgate_travel_control` for commanded travel while preserving ranger as autonomous remote-fixer type.
- v1.6.0 (2026-04-16): introduced enforced `dispatch_policy` rules so controllers self-handle local host/LAN bus jobs while rangers proactively self-handle remote incidents.
- v1.7.0 (2026-04-16): added incident-domain tagger and adaptive priority scoring (`urgency`, `risk`, `proximity`, `confidence`) for deterministic, personality-consistent assignment.
- v1.8.0 (2026-04-16): added rank-based capacity limits for `skills`, `sigils`, and `mcp.servers`; enabled skilled single-sigil specialist path (`sigil_transporter`); clarified that prime tier does not imply leadership.
- v1.9.0 (2026-04-16): introduced personality behavior overlays across classes (`*_like` patterns), local quiet-ranger mode (`ranger_local`) for host/LAN proactive operations without remote-hunt behavior, and personality interest-affinity routing for passion-aligned job selection.
- Impacted modules for v1.0.0: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`
- Impacted modules for v1.8.0: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`, `ui/control_hall.py`
- Impacted modules for v1.9.0: `core/schemas/agent_schema.py`, `core/schemas/bosscrafts_agent.schema.json`, `core/agents/model_gateway_agent.py`, `ui/control_hall.py`

## TODO

- Add exception handling workflow for temporary policy waivers.
