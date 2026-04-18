# Docs README

Canonical subsystem readme for `docs`.

## Purpose

Central location for architecture notes, decisions, runbooks, changelogs, and policy documents.

## Conventions

- Prefer lowercase snake_case markdown file names for new docs.
- Keep canonical docs here and place compatibility aliases where needed.

## Subsystem README Convention

- Each top-level subsystem should include a canonical readme named `<subsystem>_readme.md`.
- Prefer lowercase snake_case names (for example: `soundforge_readme.md`, `ui_readme.md`).
- Legacy `README.md` files may remain as compatibility docs, but canonical references should point to the subsystem readme.

## Governance

- `docs` is the canonical home for architecture, runbooks, backlog, decisions, changelog, and policy guidance.
- Subsystem readmes should deep-link here for policy-level truth rather than duplicating governance details.

## TODO

- Add freshness labels to major docs (`active`, `review-needed`, `archive-candidate`).
- Add review cadence metadata for high-impact docs.
