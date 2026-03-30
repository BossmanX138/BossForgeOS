# Archivist Stewardship

This file records Archivist maintenance operations and outputs.

## Table of Contents

- [Scope](#scope)
- [Operator Quick Guide](#operator-quick-guide)
- [Automated README Stewardship](#automated-readme-stewardship)
- [Policy Configuration](#policy-configuration)
- [Limitations](#limitations)

## Scope

- Maintained by the Archivist agent.
- Tracks stewardship-oriented maintenance notes and outputs.

## Operator Quick Guide

- Summon stewardship run:
  - `python -m core.bforge summon archivist --path "." --no-notify`
- Preview seal queue:
  - `python -m core.bforge seal preview`
- Approve latest seal:
  - `python -m core.bforge seal approve`
- Reject latest seal:
  - `python -m core.bforge seal reject --reason "needs review"`

Expected outputs from each summon include updates to:

- `docs/CHANGELOG.md`
- `docs/decisions.md`
- `docs/todos.md`
- `docs/archivistREADME.md`
- `docs/daily_ledger.md`
- `docs/delegation_notes.md`

## Automated README Stewardship

- Archivist now auto-stewards project-owned README markdown files.
- It refreshes a clickable `Table of Contents` based on `##` section headings.
- It is idempotent: existing generated TOC blocks are replaced cleanly.
- Third-party/runtime trees are skipped by default.

## Policy Configuration

Archivist policy is read from:

- `bus/state/archivist_policy.json`

Supported keys:

- `todo_scan_suffixes`
- `todo_ignore_dir_names`
- `todo_ignore_file_names`
- `readme_ignore_dir_names`
- `todo_patterns`

Example:

```json
{
  "todo_patterns": ["TODO", "FIXME", "TBD", "ACTIONITEM"],
  "todo_scan_suffixes": [".md", ".txt", ".py"],
  "todo_ignore_dir_names": [".git", ".venv", ".models", ".runtime"]
}
```

## Limitations

- TODO detection is still pattern-based and does not perform deep semantic intent analysis.
- README stewardship currently focuses on structure/navigation, not full prose rewriting.
- Seal operations still require operator approval by design.
