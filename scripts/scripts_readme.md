# Scripts README

Canonical subsystem readme for `scripts`.

## Purpose

Holds automation and maintenance scripts for development and operations.

## Current State

- Script families include startup wrappers, install/uninstall helpers, context-menu installers, release packaging helpers, and model-runtime bootstrap utilities.
- Scripts should be safe to rerun and provide actionable failure output.

## Growth Opportunities

- Separate user/operator scripts from release-engineering scripts.
- Add script ownership metadata to improve maintenance response time.

## TODO

- Add sections for `Operator Scripts` and `Build/Release Scripts` and classify each file.
- Add required environment variables and preconditions for each script family.
