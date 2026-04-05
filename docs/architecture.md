# BossForgeOS Architecture

## Overview

BossForgeOS is a modular, local-first orchestration layer with:

1. Command plane: writes command runes into the bus
2. Event plane: records system and agent events
3. State plane: rolling snapshots for daemons and services
4. SoundStage: deterministic sound event engine, system sound replacement, rollback, diagnostics
5. Control Hall GUI: web dashboard for agent status, commands, events, sound schemes, onboarding, scheduling, CI/CD, collaboration, analytics
6. VS Code extension: onboarding, agent builder, event streaming, import/export, collaborative editing, CLI integration, analytics dashboard

## Rune Bus

Root: %USERPROFILE%\\BossCrafts
- bus/events: event JSON files
- bus/commands: command JSON files
- bus/state: service state files

Durable, inspectable IPC model (no sockets/brokers required)

## Components

- core/rune_bus.py: emits commands/events, writes state snapshots, polls commands
- core/hearth_tender_daemon.py: polls commands, emits events, writes snapshots, disk threshold warnings
- core/bforge.py: CLI (status, tail, agent, os snapshot, daemon, shell, ritual, plugin)
- core/connectors/bossgate_connector.py: BossGate prototype for secure transport discovery and endpoint scanning
- core/state/agent_memory_store.py: SQLite-backed interaction memory for agents (users, employers, projects, counterpart agents)
- modules/os_snapshot.py: disk usage, Docker/WSL VHD snapshot
- core/soundstage/BossForgeOS_SoundStage: deterministic sound event engine, system sound replacement, rollback, diagnostics, HTTP API
- ui/control_hall.py: Flask server, web dashboard (agent status, commands, events, sound schemes, onboarding, scheduling, CI/CD, collaboration, analytics)
- extension/: VS Code extension (onboarding, agent builder, event streaming, import/export, collaborative editing, CLI integration, analytics dashboard)

## Safety Notes

- Docker actions are no-op if unavailable
- WSL compaction is manual-first for safety
- Command handling is target-filtered to avoid cross-agent execution

## Agent Classes and Memory

1. Core agents are service-oriented and do not require an embedded LLM to provide deterministic capabilities.
2. Prime agents are model-backed and can run reasoning/generative workloads.
3. Both classes can persist memory of interactions (projects, employers/users, and collaborating agents) via `agent_memory.sqlite3`.
4. Agent memory is designed to support continuity, relationship context, and long-term operational recall.

## Cross-References

- [README.md](../README.md): Project overview
- [docs/bossgate_connector.md](bossgate_connector.md): BossGate connector spec
- [docs/bossgate_protocol.md](bossgate_protocol.md): BossGate protocol draft
- [core/soundstage/BossForgeOS_SoundStage/ARCHITECTURE.md](../core/soundstage/BossForgeOS_SoundStage/ARCHITECTURE.md): SoundStage architecture
- [docs/gui_coverage_audit.md](gui_coverage_audit.md): GUI audit
- [docs/todos.md](todos.md): Actionable todos
- [docs/CHANGELOG.md](CHANGELOG.md): Changelog
- [docs/decisions.md](decisions.md): Decision log
