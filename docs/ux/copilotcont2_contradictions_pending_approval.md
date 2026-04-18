# copilotcont2 Contradictions Pending Approval

These items are intentionally not applied yet because they conflict with current implementation structure or contain ambiguous directives.

## 1) Full Three-Column Control Hall Re-architecture

Requested concept:

- Left nav + center canvas + right inspector panel

Current implementation:

- Left navigation + single center panel flow in ui/control_hall.py

Why approval is needed:

- Requires major layout and interaction rewrite that can break existing panel wiring and endpoint assumptions.

## 2) Navigation Taxonomy Replacement

Requested concept includes sections:

- Agents, Daemons, Rune Stream, Rituals, BossGate, MCP Servers, LLM Models, System Health, Logs & Audit, Settings

Current implementation includes different panel set and ownership:

- Agent Status, OS Snapshot, OS State, Quick Commands, Manual Command, Seal Queue, Recent Events, Bus Inspector, CI/CD, Onboarding Wizard, Scheduler, Model Chat, AgentForge, Discovery Map, Security, Sounds, Diagnostics

Why approval is needed:

- Direct renaming/removal could break user workflows and existing scripts/documentation.

## 3) "No files, no exports" vs "Implement as much as possible"

copilotcont2 text included a planning note saying no files/no exports.
Current user directive requests implementation.

Resolution chosen:

- Treated no-files wording as historical conversational context and implemented real artifacts.

## 4) Icon Style Rule Ambiguity

Rule A says no fills except active states.
Some icon descriptions call for silhouette forms that usually imply fills.

Why approval is needed:

- Need a definitive render rule for silhouette icons:
  - strict outline-only baseline
  - or selective low-opacity fills in idle state

Visual preview:

- docs/ux/icon_fill_policy_preview.html

## Approval Prompts

If approved, next implementation wave can include:

1. Full three-column Control Hall with inspector panel.
2. Navigation taxonomy migration with compatibility aliases.
3. Strict icon rendering policy finalization (outline-only vs selective fill).
