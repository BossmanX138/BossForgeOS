# BossForgeOS v1 Architecture

## Overview

BossForgeOS v1 implements a local operating layer with three core planes:

1. Command plane: writes command runes into the bus.
2. Event plane: records system and agent events.
3. State plane: keeps rolling snapshots for daemon and services.

## Rune Bus

Root location defaults to %USERPROFILE%\\BossCrafts and contains:

- bus/events: event JSON files.
- bus/commands: command JSON files.
- bus/state: service state files.

This is a durable, inspectable IPC model that does not require sockets or brokers.

## Components

- core/rune_bus.py
  - Emits commands and events.
  - Writes state snapshots.
  - Polls unread commands.

- core/hearth_tender_daemon.py
  - Polls command runes for hearth/hearth_tender targets.
  - Emits result events.
  - Writes periodic state snapshots.
  - Produces disk threshold warnings.

- core/bforge.py
  - status: show recent events.
  - tail: print latest event stream.
  - agent: enqueue agent command runes.
  - os snapshot: read environment telemetry.
  - os daemon: enqueue daemon actions.

- modules/os_snapshot.py
  - Captures disk usage.
  - Attempts Docker usage snapshot when available.
  - Captures WSL VHD location and size when present.

- ui/control_hall.py
  - GET / for summary payload.
  - GET /events for recent events.
  - POST /command for ad hoc command emission.
  - GET /health for liveness.

## Safety Notes

- Docker actions are no-op when Docker is unavailable.
- WSL compaction is intentionally manual-first to avoid unsafe privileged operations.
- Command handling is target-filtered to avoid accidental cross-agent execution.
