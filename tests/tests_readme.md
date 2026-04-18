# Tests README

Canonical subsystem readme for `tests`.

## Purpose

Contains test suites and supporting validation assets.

## Current State

- Current test coverage includes agent behavior, bus/state workflows, connector logic, and safety-related runtime behavior.
- New features should include at least one focused test and one regression guard when behavior risk is non-trivial.

## Growth Opportunities

- Expand pass-rate tracking per subsystem in CI and in local test sentinel outputs.
- Add per-platform execution notes for Linux/Windows-specific tests.

## Test Matrix

| Subsystem | Representative tests | Required fixtures/dependencies |
| --- | --- | --- |
| Rune bus + state | `tests/test_rune_bus.py`, `tests/test_os_state.py` | Temporary filesystem only |
| Core agents | `tests/test_archivist_agent.py`, `tests/test_codemage_agent.py`, `tests/test_devlot_agent.py`, `tests/test_model_gateway_agent.py` | Temporary filesystem; valid normalized agent profiles |
| Connectors | `tests/test_bossgate_connector.py` | Local UDP socket availability |
| Runtime safety / voice | `tests/test_runeforge_voice_safety.py`, `tests/test_runeforge_agent.py` | Platform-compatible runtime behavior |
| OS/system adapters | `tests/test_os_snapshot.py` | `psutil` installed |
| Security vault | `tests/test_security_sentinel_agent.py` | Windows-compatible `ctypes.windll` runtime (or platform-aware test guard) |

## Canonical Local Test Commands

- Smoke (fast sanity subset):
  - `python -m unittest tests.test_rune_bus`
- Focused (single subsystem/module):
  - `python -m unittest tests.test_archivist_agent`
- Full Python suite from repo root:
  - `python -m unittest discover -s tests`

## Current Full-Suite Notes

- `python -m unittest discover` (without `-s tests`) currently reports `Ran 0 tests`.
- The discovered full suite currently has pre-existing failures on this branch (for example agent profile validation, missing optional `psutil`, and Windows-only security vault imports on Linux).
