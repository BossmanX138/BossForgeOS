# BossForgeOS Evolution Plan (Phase 1)

This document tracks the first implementation phase for the next evolution goals:

1. Full Control Hall UI layer
2. Agent-side native bus consumers
3. Canonical OS-level state model
4. ForgeShell (REPL)
5. Mythic-industrial identity pass

## Delivered in this phase

- Canonical state model implementation:
  - `core/state/os_state.py`
  - Schema id: `bossforge.os-state.v1`
  - Includes state tree, agent manifest/runtime summary, bus file counts, and recent events.
- Control Hall API support:
  - `GET /api/os/state`
  - `POST /api/os/state/diff`
- ForgeShell prototype:
  - `core/utils/forgeshell.py`
  - Commands: `events`, `state`, `os-state`, `send`

## Delivered in this continuation slice

- Control Hall UI wiring for canonical state:
  - New `OS State` panel in Control Hall
  - Live state refresh + state diff rendering
- ForgeShell enhancements:
  - readline tab completion (when available)
  - `watch-events` live stream command
- Agent-side consumer foundation:
  - Shared loop utility `core/rune/agent_consumer.py`
  - Devlot migrated to shared consumer loop

## Delivered in this continuation slice (Bus + Archivist)

- Control Hall Bus Inspector:
  - New `Bus Inspector` panel in UI
  - New backend endpoint `GET /api/bus/inspect`
  - Shows latest commands, events, and state payloads with file-level provenance
- Agent-side consumer migration:
  - Archivist migrated to shared consumer loop utility

## Next implementation slices

### 1) Control Hall full UI layer

- Add a dedicated OS State tab with:
  - live state tree
  - agent health cards
  - state diff panel
- Add model endpoint graph visualization from model gateway state.
- Add visual bus inspector stream view (events + commands + state writes).

### 2) Agent-side consumers

- Introduce a shared consumer loop utility for command polling/dispatch.
- Migrate Archivist and Devlot first as reference agents.
- Add heartbeat/event QoS metadata (queue lag, processing time).

### 3) Canonical OS state

- Add explicit JSON schema file and validation hook.
- Add state snapshot persistence ring (time-travel baseline).
- Add state arbitration metadata for multi-agent conflicts.

### 4) ForgeShell

- Add readline completions for agent ids and commands.
- Add watch mode for inline bus events.
- Add ritual playback controls and quick state tree explorer.

### 5) Mythic-industrial identity pass

- Create unified naming and iconography guidelines.
- Harmonize Control Hall typography and color tokens.
- Add coherent lore descriptors to agent cards and shell banners.
