# Sandboxing and Safety Constraints for WindowsWorld Agent

This document describes the sandboxing and safety mechanisms used to protect your system when running the WindowsWorld agent.

## Table of Contents

- [File Operation Restrictions](#file-operation-restrictions)
- [Registry Key Protection](#registry-key-protection)
- [Observation Redaction](#observation-redaction)
- [VM and Environment Check](#vm-and-environment-check)
- [High-Risk Action Confirmation](#high-risk-action-confirmation)
- [Extending the Sandbox](#extending-the-sandbox)

## File Operation Restrictions

- File operations (create, delete, move, copy, rename, list) are restricted to whitelisted directories:
  - `C:/AgentSandbox`
  - `C:/Temp`
  - Current working directory
- Access attempts outside these directories are blocked and logged.

## Registry Key Protection

- Access to dangerous registry keys (for example `SYSTEM`, `SAM`, `SECURITY`, Windows startup paths) is blocked.
- Only safe registry operations are allowed.

## Observation Redaction

- Sensitive patterns (passwords, API keys, tokens, secrets, credentials, and related data) are redacted from observations before logging or model input.

## VM and Environment Check

- The agent can detect common virtualized environments (VMware, VirtualBox, and others).
- For maximum safety, run the agent in a VM or similarly restricted environment.

## High-Risk Action Confirmation

- High-risk actions (file deletion, registry edits, shutdown, and more) require command-code confirmation.

## Extending the Sandbox

- To add restrictions, edit `sandbox.py` and update whitelists or sensitive patterns.

These constraints keep the agent safe and limit access outside the intended sandbox.
