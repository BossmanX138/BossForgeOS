# Installer README

Canonical subsystem readme for `installer`.

## Purpose

Owns the BossForgeOS Windows installer pipeline and packaged payload helpers.

## Current State

- Builds a portable `BossForgeOS.exe` launcher with PyInstaller.
- Builds a single-file `Install BossForge_OS.exe` that extracts the packaged launcher into the user's local program directory.
- Writes release manifests under `releases/` and keeps `releases/latest/` pointed at the newest installer.

## TODO

- Add uninstall support and installed-version upgrade detection.
- Add checksum stamping for all shipped artifacts.
