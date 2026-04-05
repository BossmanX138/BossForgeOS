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

# Open Todos

This section contains actionable refactoring and optimization todos based on the current BossForgeOS codebase, recent feature additions, and GUI audit. Completed items are marked as such; new actionable items are listed below.

---

## General Agent System Improvements (2026-04-04)
- [ ] Centralize agent registration and discovery for better orchestration
- [ ] Add a unified web UI for agent management, monitoring, and configuration
- [ ] Implement semantic analysis and advanced diagnostics across all agents
- [ ] Enhance error handling, logging, and user feedback for all integrations

## 2026-04-04 Refactoring & Optimization Todos

### Distributed/Cloud Orchestration (In Progress)
- [ ] Finalize pluggable bus backend for remote/distributed operation (e.g., Redis, RabbitMQ, Azure Service Bus)
- [ ] Complete agent registration/discovery for remote bus
- [ ] Harden config for cloud endpoints and authentication
- [ ] Document distributed/cloud deployment steps

### Code Modularity & Maintainability
- [ ] Refactor core daemons and CLI for improved modularity and testability
- [ ] Extract reusable components (event streaming, onboarding, scheduling) into shared modules
- [ ] Audit and reduce code duplication across daemons, UI, and extension

### Test Coverage & Automation
- [ ] Expand unit and integration test coverage for SoundStage, Control Hall, and extension
- [ ] Add automated regression tests for onboarding, scheduler, CI/CD, and collaboration features
- [ ] Integrate test results into Control Hall analytics dashboard

### Performance & Diagnostics
- [ ] Profile and optimize event streaming and sound playback latency
- [ ] Enhance diagnostics logging and error reporting (daemon, GUI, extension)
- [ ] Add performance metrics to analytics dashboard

### Documentation & Developer Experience
- [ ] Ensure all new features are fully documented (SoundStage, onboarding, scheduler, CI/CD, collaboration)
- [ ] Add developer onboarding guide and architecture diagrams
- [ ] Cross-link all major docs for discoverability

---

## Completed Todos (2026-04-04)
- [x] Onboarding wizard (GUI & CLI)
- [x] Scheduler (GUI & CLI)
- [x] CI/CD integration (GUI)
- [x] Real-time collaboration (GUI & extension)
- [x] Analytics dashboard (GUI & extension)
- [x] Platform support (Windows/macOS/Linux)
- [x] Automated diagnostics and error handling (GUI)
- [x] Comprehensive help/documentation section (GUI)

---

For previous audits and backlog, see earlier sections below.