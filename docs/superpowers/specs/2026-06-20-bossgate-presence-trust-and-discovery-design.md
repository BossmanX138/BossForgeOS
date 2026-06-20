# BossGate Presence, Trust, and Discovery Design

Date: 2026-06-20
Status: Approved for planning
Scope: BossGate map, access, and transfer-history trust/discovery model plus shared UI language

## Goal

Define a shared BossGate presence model and operator experience for:

- sparse agent identity outside origin forge
- trust-colored node and agent visibility
- neutral beacon discovery that requires physical visit for reveal
- local unknown-message policy owned by each node operator
- radial map actions around selected agents and nodes
- consistent sealed-package presentation across BossGate surfaces

This is not a game system. It is an AI-first operating ecosystem where agents, forges, A.S.S. nodes, and future BridgeBase Alpha nodes are real operational entities. The design should add clarity, trust boundaries, recall flow, and inspectability without weakening security or sealed-agent rules.

## Product Framing

BossGate should feel like a real operator surface for an AI-native ecosystem that lives on the user's computer and can interact with other trusted or unknown nodes.

The intended operator feeling is:

- "That is one of our agents."
- "I know its name and public role, but I need it home to inspect it properly."
- "Unknown things should remain unknown until visited."
- "Trust, recall, and message acceptance are operational policy decisions."

BossGate must support memory and recognition without overexposing proprietary agent internals.

## Core Design Principles

1. Agent profiles remain sealed outside the forge of creation.
2. BossGate shows only public-facing identity for away agents: name plus public model card.
3. Discovery and communication are separate concepts.
4. Unknown or neutral node identity is not revealed by remote contact.
5. Trust state must be visually obvious and consistent across surfaces.
6. Local owner policy controls whether unknown locations may message the current node.
7. BossGate surfaces should present agents as crafted protected entities, not generic files.

## Shared Presence Model

BossGate should normalize every visible map/history/access entity into a shared presence model with two top-level categories:

- `node_presence`
- `agent_presence`

Each presence record should carry enough information for map rendering, access controls, and transfer-history display without requiring three separate ad hoc payload shapes.

### Node Presence

A node presence represents:

- a BossForge
- an A.S.S. instance
- a future BridgeBase Alpha node

Recommended fields:

- `presence_kind`: `node`
- `node_id`
- `node_type`: `bossforge` | `ass` | `bridgebase_alpha` | `unknown`
- `discovery_state`: `unrevealed_beacon` | `revealed`
- `trust_state`: `own` | `trade_linked` | `unknown` | `neutral_unaffiliated`
- `visited`: boolean
- `accept_unknown_messages`: boolean
- `supports_messaging`: boolean
- `supports_transfer`: boolean
- `supports_visit`: boolean
- `display_name`: optional, only when revealed
- `public_summary`: optional, only when revealed

Rules:

- Neutral or unaffiliated nodes begin as grey beacons.
- Their identity remains hidden until one of the operator's assets performs an actual visit/contact event that counts as a visit.
- Remote messaging alone never reveals the node.
- Remote probe alone never reveals the node.
- Revealed node identity may then be displayed in future map and history views.

### Agent Presence

An agent presence represents an agent as seen through BossGate while away from its forge of creation.

Recommended fields:

- `presence_kind`: `agent`
- `agent_id`
- `agent_name`
- `origin_node_id`
- `current_node_id`
- `trust_state`: `own` | `trade_linked` | `unknown`
- `public_identity_card`
- `model_card`
- `disclosure_posture`
- `inspection_state`: `origin_forge_required` | `origin_forge_available`

Rules:

- Outside the origin forge, BossGate may show only `agent_name` plus public identity/model-card information.
- BossGate must never expose the full internal profile outside the forge of creation.
- Returning the agent home enables inspection through AgentForge, not through BossGate itself.
- BossGate should support personal recognition such as "that's Promethius" without exposing private build data.

## Trust and Color Language

BossGate should use a single shared trust-color system across map, access, and history.

- `green`: your forge's agents or nodes
- `blue`: trade-linked forge assets or nodes
- `red`: assets or nodes from unknown forges after reveal/risk classification
- `grey`: neutral or unaffiliated unrevealed beacon

Interpretation:

- Green means known and owned by the current operator's ecosystem.
- Blue means known and externally trusted through trade or equivalent relationship.
- Red means known but not trusted by default.
- Grey means unresolved presence whose identity is still hidden.

Grey should indicate beacon-only visibility. The map shows a signal/beacon, not whether it is a forge, A.S.S., or BridgeBase Alpha, until visited.

## Discovery and Messaging Policy

Discovery state and message policy must be separate concerns.

### Discovery

- Unrevealed grey beacon identity is hidden until actual visit.
- Messaging does not reveal beacon identity.
- Remote probe does not reveal beacon identity.
- Transfer attempt alone does not reveal beacon identity unless it includes a successful visit-class event by design.

### Unknown Message Policy

Each node owner sets policy only for their own node or nodes.

Policy:

- `accept messages from unknown locations`: `off` by default

Meaning:

- If `off`, unknown unresolved locations may not message the current node.
- If `on`, unknown unresolved locations may message the current node.
- Turning it `on` does not reveal who or what the unknown location is.
- This is not a bilateral or negotiated policy. Each owner configures only their own node behavior.

This policy should apply to:

- BossForges
- A.S.S. instances
- future BridgeBase Alpha nodes

## Surface Design

### BossGate Map

The map becomes the live operational canvas for presences.

Requirements:

- Render nodes and agents using the shared trust/discovery model.
- Show sparse public card information for away agents.
- Show grey beacon-only markers for unrevealed neutral/unaffiliated nodes.
- Clicking a presence opens a radial command menu centered on the selected presence.

#### Radial Command Menu

The radial menu is the primary interaction pattern for map selections.

For agents, the center should show:

- agent name
- short trust/ownership cue
- sparse state cue such as "model card only while abroad"

Candidate actions around the ring:

- `Send Message`
- `Recall Home`
- `Route Orders`
- `View Model Card`
- `Hold / Quarantine`
- `Trade History`

For unrevealed grey beacons:

- center remains anonymous
- available actions are limited by discovery state and local unknown-message policy
- no action may reveal identity without a visit

### BossGate Access

The access surface becomes the policy/control layer behind map behavior.

Responsibilities:

- set local unknown-message acceptance policy
- manage trust relationships such as trade-linked forges
- perform package / transfer / install operations
- expose role/permission controls for relevant BossGate operations

Presentation rules:

- use the same sealed-package language established in AgentForge
- visually reinforce that moved agents are protected crafted entities
- keep trust/discovery labels consistent with map and history

### Transfer History

Transfer history becomes a memory ledger, not just a raw log.

Requirements:

- display trust context at time of event
- preserve whether an event involved own, trade-linked, unknown, or unresolved presence
- show agent name + model card only when allowed
- preserve grey-beacon ambiguity for unresolved events

Historical interpretation rule:

- if a beacon was unresolved at the time of contact, earlier history entries stay meaningful as unresolved events
- once later visit reveals identity, future entries can show the identity without retroactively pretending the earlier event was known at the time

## Shared UI Language

BossGate should reuse the sealed-package presentation language added to AgentForge.

Shared cues:

- protected / sealed status chips
- sparse public card summary blocks
- trust-color badges
- clear distinction between public model-card visibility and origin-forge inspection availability

This is intended to make agents feel like the same protected crafted entities everywhere in the ecosystem.

## State Transitions

The following transitions must be explicit and testable:

### Node Discovery

- `unrevealed_beacon` -> `revealed` only after actual visit

Not allowed:

- message-only reveal
- probe-only reveal

### Agent Inspection

- `origin_forge_required` -> `origin_forge_available` when agent is back at the forge of creation

Inspection remains an AgentForge concern. BossGate may initiate recall or display status, but should not bypass the sealed-agent contract.

### Unknown Message Policy

- local owner toggles `accept_unknown_messages`
- affects whether current node accepts unknown inbound messages
- does not affect reveal state

## Architecture Boundaries

This work should be implemented as a shared BossGate presence/trust layer rather than separate one-off UI patches.

Recommended implementation boundaries:

1. Shared presence normalization layer
   - produces node/agent presence objects for map, history, and access
2. Shared trust/discovery classifier
   - determines color state, reveal state, and sparse identity allowance
3. Shared radial-menu renderer/controller
   - supports different action sets for nodes vs agents
4. Shared public-card renderer
   - renders sparse public identity/model-card views consistently
5. Local policy storage/adapter
   - stores node-level unknown-message acceptance settings

## Testing and Verification

Verification should cover backend rules, route payloads, and UI rendering behavior.

### Backend Tests

- unrevealed beacon remains anonymous after remote messaging
- unrevealed beacon remains anonymous after probe
- reveal occurs only after visit
- trust-state classification maps correctly to color states
- away agents expose only sparse public information
- origin-forge inspection state changes only when agent is home
- local unknown-message policy affects acceptance behavior only

### Route / Payload Tests

- map payload exposes only permitted fields for unrevealed beacons
- map payload exposes only sparse public identity for away agents
- access payload includes local unknown-message policy state
- history payload preserves unresolved-event ambiguity when appropriate

### UI Verification

- map renders green/blue/red/grey presence states correctly
- radial menu opens centered on selected presence
- action set changes appropriately for agent vs node vs grey beacon
- sparse public card language is consistent with AgentForge sealed-package language
- grey beacon presentation does not leak node identity

## Out of Scope

- weakening sealed-agent visibility rules
- full remote inspection of agent internals outside origin forge
- bilateral trust-policy negotiation between operators
- redefining AgentForge inspection semantics
- BridgeBase Alpha implementation details beyond compatibility with this model

## Recommended Next Step

Write an implementation plan that:

- defines the normalized BossGate presence payload
- identifies current map/access/history data sources to adapt
- scopes the radial-menu component work
- adds policy storage for local unknown-message handling
- stages backend rule tests before UI integration
