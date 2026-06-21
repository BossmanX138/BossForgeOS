# Releases README

Canonical subsystem readme for `releases`.

## Purpose

Stores release-ready bundles, manifests, and packaging metadata.

## Current State

- Keep release artifacts immutable once published.
- Include changelog linkage for each release package.
- Canonical stamped artifacts live under `releases\v<version>\`.
- `releases\latest\` is a mutable convenience alias for the newest packaged installer.
- Launcher-era `BossForgeLauncher*.exe` files should be moved under `releases\archive\launcher-era\` when the modern installer pipeline is rebuilt.

## Growth Opportunities

- Standardize release manifest schema for package integrity and provenance.

## TODO

- Add release manifest template with checksum, source commit, and signer metadata.
