Here is a detailed TODO plan for fixing each BossForgeOS limitation:

1. Local-First (No Distributed/Cloud Orchestration)

Research distributed bus/message queue options (e.g., Redis, RabbitMQ, Azure Service Bus)
Design a pluggable bus backend (local file, remote queue)
Implement remote bus backend and agent registration/discovery
Add config for cloud endpoints and authentication
Update docs for distributed/cloud deployment

2. Manual Onboarding (Token/Voice Profile Setup)

Add onboarding CLI wizard for secrets/tokens and voice profiles
Implement validation and auto-detection for missing onboarding steps
Provide onboarding status in Control Hall UI
Update docs with onboarding flow screenshots/examples

3. No Built-in Scheduler

Evaluate Python schedulers (APScheduler, Celery, etc.)
Integrate scheduler with bus and agent command system
Add CLI/Control Hall UI for scheduling tasks/rituals
Document scheduling features and usage

4. Limited Error Handling

Audit CLI and agent error handling for unhandled exceptions
Add user-friendly error messages and recovery suggestions
Log errors to bus/events and Control Hall UI
Add automated diagnostics for common setup issues

5. Third-Party Code Noise in TODOs

Update Archivist/todo extraction to ignore .venv, site-packages, and external folders
Add config for custom ignore patterns
Document filtering behavior

6. No Built-in CI/CD

Add GitHub Actions/other CI templates to repo
Provide CLI for running tests/lint locally
Integrate test results into Control Hall UI
Document CI/CD setup and usage

7. Windows-Centric Features

Audit all Windows-only features
Add macOS/Linux equivalents or document alternatives
Use cross-platform packaging tools (PyInstaller, etc.)
Update docs for platform-specific steps

8. No Real-Time Collaboration

Research collaborative agent/command models (websockets, shared bus, etc.)
Prototype multi-user Control Hall or CLI sessions
Add user/session management and permissions
Document collaboration features and limitations

9. Documentation Gaps


# 2026-03-30 Feature Audit: Actionable TODOs

## Distributed/Cloud Orchestration (Partial)
- Research and prototype a pluggable bus backend for remote/distributed operation (e.g., Redis, RabbitMQ, Azure Service Bus).
- Implement agent registration/discovery for remote bus.
- Add config options for cloud endpoints and authentication.
- Document distributed/cloud deployment steps.

## Onboarding Automation (Partial)
- Implement a CLI onboarding wizard for secrets/tokens and voice profiles.
- Add validation and auto-detection for missing onboarding steps.
- Integrate onboarding status into Control Hall UI.
- Add onboarding flow documentation and screenshots.

## Scheduler (Missing)
- Evaluate and select a Python scheduler (APScheduler, Celery, etc.).
- Integrate scheduler with bus and agent command system.
- Add CLI and Control Hall UI for scheduling tasks/rituals.
- Document scheduling features and usage.

## Error Handling (Partial)
- Audit CLI and agent error handling for unhandled exceptions.
- Add user-friendly error messages and recovery suggestions.
- Log errors to bus/events and Control Hall UI.
- Add automated diagnostics for common setup issues.

## TODO Noise Filtering (Partial)
- Update Archivist/todo extraction to ignore .venv, site-packages, and external folders.
- Add config for custom ignore patterns.
- Document filtering behavior.

## CI/CD (Missing)
- Add GitHub Actions or other CI templates to the repo.
- Provide CLI for running tests/lint locally.
- Integrate test results into Control Hall UI.
- Document CI/CD setup and usage.

## Cross-Platform Support (Partial)
- Audit all Windows-only features and document them.
- Add macOS/Linux equivalents or document alternatives.
- Use cross-platform packaging tools (PyInstaller, etc.).
- Update docs for platform-specific steps.

## Real-Time Collaboration (Missing)
- Research collaborative agent/command models (websockets, shared bus, etc.).
- Prototype multi-user Control Hall or CLI sessions.
- Add user/session management and permissions.
- Document collaboration features and limitations.

## Documentation Gaps (Partial)
- Audit docs for missing/unclear features.
- Add usage examples, screenshots, and onboarding guides.
- Automate doc updates from code/comments where possible.