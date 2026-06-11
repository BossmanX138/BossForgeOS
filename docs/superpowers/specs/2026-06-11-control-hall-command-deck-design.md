# Control Hall Command Deck Design

Date: 2026-06-11
Status: Approved for implementation planning

## Goal

Replace the minimal Agent Status landing panel with an operational Command Deck
that answers one question first:

> What needs the operator's attention now?

The dashboard must preserve BossForgeOS's blackstone visual identity, expose live
agent and system state without distracting movement, and let an authorized
operator inspect and resolve supported decisions without losing dashboard
context.

## Scope

This first UI phase implements:

1. the Command Deck as the default Control Hall view
2. summary metrics for agents, running work, pending decisions, and active risk
3. adjacent Needs Your Decision and Quick Commands panels
4. adjacent Work in Motion and System Load panels
5. reusable Command Deck panel styling and status states
6. an overlay side drawer for decision and work-item details
7. risk-based confirmation for supported consequential actions
8. calm live updates
9. explicit normal, stale, no-data, and failed data states
10. responsive and keyboard-accessible behavior
11. a normalized dashboard read API
12. narrowly typed decision-resolution APIs for supported subsystems
13. focused route, rendering, interaction, and accessibility tests

This phase does not:

1. redesign every Control Hall panel
2. remove or replace the existing left navigation
3. introduce user-configurable dashboard layouts
4. add drag-and-drop panel placement
5. infer approval capabilities from arbitrary event text
6. provide a generic endpoint that can approve any action
7. replace subsystem policy or authorization enforcement
8. implement historical analytics beyond the data needed by the dashboard

## Approved Direction

The selected direction is **Command Deck**.

The dashboard prioritizes:

1. decisions requiring operator attention
2. commands that can resolve or investigate those decisions
3. work currently in motion
4. system context and load

The full agent fleet remains available through existing Control Hall views and
through details opened from Work in Motion. It does not dominate the landing
screen.

## Information Architecture

### Summary row

Four compact panels appear first:

1. **Agents**
   - total known agents
   - active agent count
2. **Running**
   - active task count
   - healthy or degraded state
3. **Awaiting**
   - unresolved decisions requiring operator action
4. **Risk**
   - count and highest current severity

### Primary action row

**Needs Your Decision** is the largest panel on the left.

It shows a short ordered list of unresolved items with:

1. concise title
2. one-line reason or requested operation
3. severity text
4. age
5. originating subsystem or agent

**Quick Commands** sits directly beside it.

Initial commands:

1. Create mission
2. Dispatch agent
3. Open diagnostics
4. Resolve selected

Quick Commands must call existing typed workflows or navigate to their existing
Control Hall views. It must not bypass validation, authorization, or safety
checks.

### Operational row

**Work in Motion** appears below Needs Your Decision and shows:

1. agent or owner
2. current task
3. progress or state
4. blocked state when present

**System Load** appears beside it and summarizes current machine pressure from
the OS snapshot data.

## Visual System

### Base palette

Use the existing BossForgeOS theme:

1. blackstone background and dark panels
2. BossForge gold for identity
3. amber for warning
4. red for critical or failed
5. neon green for pointer hover
6. neutral gray for normal and informational states

Blue is excluded from the Command Deck status language. Normal and
informational content share the neutral border.

### Panel borders

Every Command Deck panel has:

1. a permanent `9px` gold left border
2. `1px` top, right, and bottom borders
3. neutral thin borders for normal and informational content
4. amber thin borders for warning content
5. red thin borders for critical or failed content

A panel uses the highest severity of the information it contains. Individual
rows retain text badges so severity is not communicated through border color
alone.

### Hover and focus

Pointer hover:

1. moves the panel upward slightly
2. scales it to approximately `1.018`
3. turns the top, right, and bottom borders neon green
4. preserves the `9px` gold left border
5. temporarily overrides severity border color
6. restores severity border color when the pointer leaves

The effect must remain subtle enough that adjacent content does not visibly
reflow.

Keyboard focus uses a separate high-contrast focus indicator rather than
reusing the neon-green hover treatment.

When reduced motion is requested, the panel does not translate or scale.

## Detail Drawer

Clicking a decision or work item opens an overlay side drawer from the right.
The dashboard remains visible but visually subdued behind it.

The drawer contains:

1. exact item title and stable identifier
2. severity and current state
3. origin, owner, policy, or mission context
4. requested scope or operation
5. relevant evidence and timestamps
6. supported recovery or resolution actions

### Drawer framing

The drawer uses matching gold rails:

1. left rail: `9px`
2. right rail without overflow: `9px`
3. right rail with overflow: `4px` border plus `5px` gold scrollbar
4. scrollbar track: dark neutral
5. scrollbar thumb hover: brighter gold

The UI detects vertical overflow and toggles the narrow right-border state. The
combined right border and scrollbar must retain a `9px` visual width.

### Drawer behavior

1. The drawer header and action footer remain visible while its body scrolls.
2. `Escape` closes the drawer when no blocking confirmation is active.
3. Closing returns focus to the item that opened it.
4. Opening another item updates the existing drawer instead of stacking
   drawers.
5. Nested drawers and nested dialogs are not allowed.

## Consequential Actions

Confirmation is risk-based:

1. low-risk, reversible actions execute immediately
2. warning and critical actions require confirmation
3. irreversible actions require explicit confirmation with exact outcome text

Confirmation occurs inline inside the drawer where practical. A modal alert
dialog is reserved for irreversible loss or an action that cannot safely remain
inside the drawer.

Action labels describe the result, such as:

1. Approve once
2. Deny and close
3. Retry connection
4. Open diagnostics

Successful actions update the item state and show concise feedback. Failed
actions preserve the drawer context and state what failed and how to recover.

## Data Contract

Add a normalized read endpoint:

`GET /api/control_hall/dashboard`

The response includes:

```json
{
  "generated_at": "2026-06-11T20:00:00Z",
  "summary": {
    "agents_total": 12,
    "agents_active": 10,
    "tasks_running": 8,
    "decisions_pending": 3,
    "risk_count": 1,
    "highest_severity": "critical"
  },
  "decisions": [],
  "work_items": [],
  "system_load": {},
  "sources": {}
}
```

### Normalized decision

Each decision includes:

1. `id`
2. `kind`
3. `title`
4. `summary`
5. `severity`
6. `state`
7. `created_at`
8. `source`
9. `owner`
10. `details`
11. `evidence`
12. `allowed_actions`
13. `requires_confirmation`

`allowed_actions` is generated by the server after BossGate capability checks.
The client must not manufacture or broaden available actions.

### Normalized work item

Each work item includes:

1. `id`
2. `owner`
3. `title`
4. `state`
5. `progress`
6. `blocked_reason`
7. `updated_at`
8. `source`

### Source health

Each contributing source reports:

1. `state`: `current`, `stale`, `no_data`, or `failed`
2. `last_success_at`
3. `checked_at`
4. `message`
5. `retryable`

The aggregation layer must not convert a source failure into an empty successful
result.

## Resolution API

Supported decisions resolve through a typed route:

`POST /api/control_hall/decisions/<decision_id>/actions/<action_id>`

The request includes:

1. acting user identifier
2. expected decision version or updated timestamp
3. confirmation acknowledgement when required
4. optional action-specific input defined by the server contract

The server:

1. reloads the underlying decision
2. verifies that it remains pending
3. checks the expected version to prevent stale resolution
4. verifies BossGate permissions
5. delegates to the owning subsystem
6. records an audit event
7. returns the normalized updated decision

The route supports only registered action handlers. Unknown kinds and actions
are rejected. Authority conflicts, Runeforge approvals, and future decision
types remain separate handlers with their own policy enforcement.

## Data Sources

The dashboard aggregation service adapts existing data from:

1. `/api/status`
2. `/api/agent_tasks`
3. `/api/snapshot`
4. `/api/events`
5. `/api/delegation/flow`
6. Runeforge pending approval state
7. model gateway authority escalation records when available
8. BossGate capabilities for the acting user

The UI consumes the normalized dashboard endpoint rather than coordinating all
of these requests directly.

## Calm Live Updates

The dashboard refreshes automatically without destabilizing interaction.

Rules:

1. values may refresh in place
2. routine updates do not announce themselves repeatedly
3. cards do not reorder while hovered, keyboard-focused, or while a drawer is
   open
4. queued ordering changes apply after interaction ends
5. new critical decisions appear immediately
6. an open drawer retains the same item identifier
7. if the open item changes, its content updates without stealing focus
8. if the open item resolves elsewhere, the drawer shows the resolved state
   rather than disappearing
9. every panel exposes its last update time

The first implementation may use bounded polling. The view model and update
logic must remain transport-independent so a future push channel can replace
polling without redesigning the UI.

## Data Reliability States

### Current

Show current values with neutral status borders.

### Stale

1. retain the last valid value
2. mark it `STALE` in text
3. show the last successful update time
4. use amber status borders
5. offer Retry and Open diagnostics when supported

### No data

1. state that the request succeeded
2. explain that no records matched or exist
3. use neutral status borders
4. provide an appropriate action such as Clear filters or Refresh

### Failed

1. state the exact failure category in text
2. use red status borders
3. avoid showing a retained value when it could imply unsafe current state
4. show the failure time
5. offer Reconnect, Retry, or Open diagnostics when supported

No-data and failed states must remain distinct.

## Responsive Behavior

### Wide screens

1. retain the approved two-column rows
2. use the overlay side drawer

### Medium screens

1. stack dashboard panels as needed
2. keep Quick Commands directly after Needs Your Decision
3. expand the drawer to approximately 60-70 percent of the viewport

### Narrow screens

1. use a single-column dashboard
2. present the drawer as a full-screen detail surface
3. preserve all evidence and actions
4. avoid horizontal page scrolling

Reflow must not remove information or functionality.

## Accessibility

1. Interactive panels are reachable by `Tab`.
2. `Enter` and `Space` open the focused panel.
3. Focus order follows visual and semantic order.
4. Focus indicators meet WCAG contrast and area requirements.
5. Opening the drawer moves focus to its heading or first appropriate control.
6. The overlay drawer traps focus while open.
7. Closing restores focus to the trigger.
8. Live updates never steal focus.
9. Critical status messages use restrained, appropriate live-region semantics.
10. Severity and errors always include text.
11. Controls meet minimum target size and spacing requirements.
12. Reduced-motion preferences disable decorative movement.
13. The dashboard remains usable at 200 percent text zoom and narrow reflow.

## Code Organization

The current Control Hall page is a large `render_template_string` module. This
phase introduces bounded units without redesigning the entire application:

1. `modules/control_hall_dashboard/service.py`
   - aggregates and normalizes dashboard data
2. `modules/control_hall_dashboard/decision_registry.py`
   - maps supported decision kinds and actions to typed handlers
3. `assets/ui/control_hall_command_deck.css`
   - Command Deck, drawer, status, responsive, and accessibility styles
4. `assets/ui/control_hall_command_deck.js`
   - rendering, polling, calm-update queue, drawer, overflow detection, and
     focus management
5. `ui/control_hall.py`
   - serves the assets and exposes thin dashboard routes

Existing unrelated Control Hall views remain in place.

## Error Handling

1. Aggregation errors are isolated by source.
2. One failing source does not erase healthy panels.
3. Route errors return stable machine codes and concise operator-facing text.
4. Resolution conflicts return the current decision instead of silently
   overwriting newer state.
5. Authorization failures never reveal unavailable actions as executable.
6. Client rendering escapes all server-provided text.
7. Polling stops or backs off when the page is hidden or repeated failures occur.

## Testing

### Service tests

Cover:

1. summary aggregation
2. severity ordering
3. current, stale, no-data, and failed source normalization
4. partial source failure
5. deterministic decision and work-item ordering

### Route tests

Cover:

1. dashboard response schema
2. authorized supported actions
3. unauthorized actions
4. unknown decision kinds and action identifiers
5. stale version conflicts
6. successful audit recording
7. subsystem action failure

### Frontend tests

Cover:

1. panel rendering and approved hierarchy
2. neutral, warning, critical, stale, no-data, and failed states
3. hover and keyboard focus distinctions
4. drawer open, close, and focus restoration
5. adaptive `9px` right rail with `4px` border and `5px` scrollbar
6. risk-based confirmation
7. calm update ordering while interaction is active
8. reduced-motion behavior
9. responsive layouts
10. text and HTML escaping

### Manual verification

Verify in the local browser at wide, medium, and narrow widths:

1. no unexpected page-level horizontal scrolling
2. panel bulge does not cause layout reflow
3. drawer rails and scrollbar retain equal visual weight
4. keyboard-only completion of a supported decision
5. screen-reader announcements remain useful and non-repetitive
6. stale data cannot be mistaken for current data

## Acceptance Criteria

The design is complete when:

1. Agent Status opens as the approved Command Deck.
2. Quick Commands is adjacent to Needs Your Decision.
3. All panels use the approved gold identity rail and severity border system.
4. Hover uses neon green on only the three thin borders.
5. Blue is absent from Command Deck status semantics.
6. Item details open in the approved side drawer.
7. The drawer uses matching gold rails and adaptive `4px + 5px` overflow rail.
8. Warning and critical actions require confirmation.
9. Live updates follow the calm-update rules.
10. Current, stale, no-data, and failed states are visibly and textually
    distinct.
11. Responsive layouts preserve information and actions.
12. Keyboard and reduced-motion behavior meet the approved accessibility rules.
13. Existing Control Hall views and routes continue to work.
