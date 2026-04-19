# Archivist Stewardship

The Archivist agent maintains, audits, and stewards all project documentation, feature logs, and actionable todos. It ensures BossForgeOS documentation reflects the current system state, including SoundStage, GUI, VS Code extension, and all advanced features.

## Table of Contents

- [Scope](#scope)
- [Operator Quick Guide](#operator-quick-guide)
- [Automated README Stewardship](#automated-readme-stewardship)
- [Policy Configuration](#policy-configuration)
- [Limitations](#limitations)
- [Cross-References](#cross-references)

## Scope

- Maintained by the Archivist agent
- Tracks stewardship-oriented maintenance notes, outputs, and documentation updates
- Integrates with SoundStage, Control Hall GUI, and VS Code extension for full coverage

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

- Archivist auto-stewards all project-owned README markdown files
- Refreshes clickable Table of Contents based on `##` section headings
- Idempotent: existing TOC blocks are replaced cleanly
- Third-party/runtime trees are skipped by default

## Policy Configuration

Archivist policy is read from:

- `bus/state/archivist_policy.json`

Supported keys:

- `todo_scan_suffixes`
- `todo_ignore_dir_names`
- `todo_ignore_file_names`
- `todo_ignore_globs`
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

- TODO detection is still heuristic/pattern-based (not full semantic intent)
- README stewardship focuses on structure/navigation, not full prose rewriting
- Seal operations require operator approval by design

## Cross-References

- [README.md](../README.md): Project overview
- [docs/architecture.md](architecture.md): System architecture
- [core/soundstage/BossForgeOS_SoundStage/README.md](../core/soundstage/BossForgeOS_SoundStage/README.md): SoundStage
- [docs/gui_coverage_audit.md](gui_coverage_audit.md): GUI audit
- [docs/todos.md](todos.md): Actionable todos
- [docs/CHANGELOG.md](CHANGELOG.md): Changelog
- [docs/decisions.md](decisions.md): Decision log
