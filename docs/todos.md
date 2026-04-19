# Open Todos

Curated by Archivist from actionable TODO/FIXME/TBD signals.

Generated: 2026-04-19 19:28:34
Total actionable: 79
General backlog: 70
Test debt: 9

## Priority Backlog

- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:88 :: TODO_PATTERNS = ["TODO", "FIXME", "TBD"]
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:496 :: if stripped.lower() in {"todo", "fixme", "tbd", "## todo", "# todo"}:
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:509 :: # Keep explicit TODO/FIXME markers as actionable by default.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:510 :: if re.search(r"\b(todo|fixme|tbd)\b", lower):
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:518 :: if "fixme" in lower or any(k in lower for k in ["security", "crash", "critical", "data loss"]):
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:588 :: "Curated by Archivist from actionable TODO/FIXME/TBD signals.",
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/codemage_agent.py:436 :: todo_hits = [line.strip() for line in lines if "TODO" in line.upper() or "FIXME" in line.upper()][:10]
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] /home/runner/work/BossForgeOS/BossForgeOS/core/rune/discovery_handoff.py:20 :: TODO_LINE_RE = re.compile(r"\b(?:TODO|FIXME|TBD)\b", re.IGNORECASE)
  next: Create fix plan, implement patch, and add regression tests
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:5 :: Implement BossCrafts Protocol v1 versioning and compatibility checks
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:6 :: Add structured event schemas to Rune Bus (define event types, schemas)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:7 :: Implement agent execution trace logging (per-agent, per-event)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:8 :: Add per-agent SLA/health scoring logic (daemon/agent health monitors)
  next: Review context, confirm scope, and create a concrete next task
- [runeforge][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:9 :: Define canonical OS state model (schema, serialization, diff)
  next: Validate model/runtime impact and propose configuration update
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:10 :: Implement time-travel state diff and restore
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:11 :: Add audit-grade immutable logs (append-only, signed)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:12 :: Implement signed agent manifests (manifest schema, signing tool)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:16 :: Build live dashboards (agent status, event streaming, analytics)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:17 :: Implement drag-and-drop agent wiring UI
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:18 :: Add visual bus inspector (event/topic explorer)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:19 :: Build soundstage mixer UI (routing, EQ, diagnostics)
  next: Review context, confirm scope, and create a concrete next task
- [runeforge][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:20 :: Add model endpoint health dashboard (status, metrics)
  next: Validate model/runtime impact and propose configuration update
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:21 :: Implement runtime topology view (graph of daemons/agents)
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:24 :: Refactor agents to subscribe/react to bus events (consumables)
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:25 :: Implement agent telemetry emission (structured logs, metrics)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:26 :: Add capability-scoped lease system (token/lease manager)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:27 :: Implement per-agent sandboxing (resource limits, isolation)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:28 :: Add config overlays and daemon orchestration profiles (profile loader)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:31 :: Implement ForgeShell REPL (command parser, bus/event integration)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:32 :: Add autocompletion and inline bus event streaming
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:33 :: Build state tree viewer and agent log inspector
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:34 :: Implement ritual recording/playback (ritual engine)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:35 :: Add developer hot-reload for agents/daemons
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:40 :: Add narrative-driven onboarding and persona prompts
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_TODO_LIST.md:44 :: Each TODO is staged for agent delegation. Agents can be assigned to design, implement, test, or document each item as discrete tasks.
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:5 :: Add structured event schemas and agent execution traces
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:6 :: Add per-agent SLAs and health scoring
  next: Review context, confirm scope, and create a concrete next task
- [runeforge][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:7 :: Add canonical OS state model (unified schema, time-travel diff, arbitration)
  next: Validate model/runtime impact and propose configuration update
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:8 :: Add audit-grade immutable logs and signed agent manifests
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:11 :: Build full Control Hall UI layer (React/HTMX/Flask hybrid)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:12 :: Add visual bus inspector, agent wiring graph, runtime topology view
  next: Review context, confirm scope, and create a concrete next task
- [runeforge][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:13 :: Add model endpoint health dashboard
  next: Validate model/runtime impact and propose configuration update
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:16 :: Add agent-side consumers (agents subscribe/react to bus events, emit telemetry)
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:17 :: Add capability-scoped leases and per-agent sandboxing
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:18 :: Add config overlays and daemon orchestration profiles
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:21 :: Implement ForgeShell (persistent REPL: bus events, agent logs, rituals, state tree, autocompletion)
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:22 :: Add time-travel debugging and state diff tools
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/ENTERPRISE_ROADMAP.md:23 :: Add ritual recording/playback and developer hot-reload
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/.github/copilot-instructions.md:2 :: Verify that the copilot-instructions.md file in the .github directory is created.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/.github/copilot-instructions.md:36 :: Create and Run Task
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/.github/copilot-instructions.md:49 :: Ensure Documentation is Complete
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/m365_copilot_connector/README.md:38 :: - Added extension hook: `DevlotAutonomyHooks` for TODO automation and recommendation events.
  next: Convert this note into a tracked work item with owner/date
- [archivist][medium] /home/runner/work/BossForgeOS/BossForgeOS/docs/autonomous_work_session.md:14 :: - Implemented policy TODO batch in `docs/AgentForge_readme.md`:
  next: Update documentation section and cross-link related docs
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/docs/progress_report_2026-04-04.md:6 :: - Progress will be updated in this log and in the main todo list as agents complete their work.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/BossCrafts_Devlot_MkII.md:49 :: - Documents completed work and updates TODO lists.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/BossCrafts_Devlot_MkII.md:52 :: - If no one responds to his suggestions via the bus within a reasonable time, he will append his suggestions directly to the TODO item he just cleared, clearly stating that Devlot completed the task and these are suggestions (not new TODOs 
  next: Convert this note into a tracked work item with owner/date
- [codemage][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:153 :: "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
  next: Open implementation task with acceptance criteria and tests
- [codemage][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/master_agents.py:17 :: "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/README.md:93 :: ### TODO
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/.github/copilot-instructions.md:59 :: - If any tools are available to manage the above todo list, use it to track progress through this checklist.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/.github/copilot-instructions.md:61 :: - Read current todo list status before starting each new step.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/m365_copilot_connector/declarativeAgent.json:17 :: { "name": "DevlotAutonomyHooks", "description": "Hooks for Devlot autonomous TODO processing and recommendation events." }
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/docs/delegation_plan_2026-04-04.md:5 :: | Todo Item                                                        | Assigned Agent(s)      | Status      |
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/docs/BossCrafts_BossForgeOS_bp.txt:1145 :: # TODO: handle $data.command and $data.args here
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/BossCrafts_Devlot_MkII.md:35 :: - Supports runtime hook `DevlotAutonomyHooks` for TODO completion flow and post-task suggestion events
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:552 :: if "todo" in lower:
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/rune/hands_on_runtime.py:58 :: item["resolution"] = "Auto-processed discovery handoff TODO"
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/rune/discovery_handoff.py:22 :: r"(?:TODO\s*[\[(]\s*(?P<todo_owner>[a-zA-Z_\- ]+)\s*[\])]"
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] /home/runner/work/BossForgeOS/BossForgeOS/core/rune/discovery_handoff.py:183 :: "title": f"TODO handoff from {current_agent}",
  next: Convert this note into a tracked work item with owner/date
- [devlot][low] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/archivist_agent.py:520 :: if "tbd" in lower or any(k in lower for k in ["later", "investigate", "review"]):
  next: Review context, confirm scope, and create a concrete next task
- [devlot][low] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/codemage_agent.py:516 :: if "TODO" in upper or "OPEN" in upper or "TBD" in upper:
  next: Convert this note into a tracked work item with owner/date

## Test Debt

- [test_sentinel][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/test_sentinel_agent.py:177 :: pattern = re.compile(r"TODO|FIXME|TBD", re.IGNORECASE)
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][high] /home/runner/work/BossForgeOS/BossForgeOS/core/agents/test_sentinel_agent.py:196 :: "severity": "high" if "fixme" in line.lower() else "medium",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] /home/runner/work/BossForgeOS/BossForgeOS/tests/test_archivist_agent.py:119 :: (project / "notes.txt").write_text("todo\n", encoding="utf-8")
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] /home/runner/work/BossForgeOS/BossForgeOS/tests/test_archivist_agent.py:295 :: "# TODO: implement archival retention policy\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] /home/runner/work/BossForgeOS/BossForgeOS/tests/test_archivist_agent.py:329 :: "# TODO: implement command routing\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] /home/runner/work/BossForgeOS/BossForgeOS/tests/test_codemage_agent.py:31 :: "args": {"language": "python", "content": "print('x')\n# TODO: improve"},
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] /home/runner/work/BossForgeOS/BossForgeOS/tests/test_archivist_agent.py:248 :: "# TODO: real work item\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] /home/runner/work/BossForgeOS/BossForgeOS/tests/test_archivist_agent.py:255 :: self.assertIn("TODO: real work item", str(todos[0].get("text", "")))
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] /home/runner/work/BossForgeOS/BossForgeOS/tests/test_archivist_agent.py:291 :: "- [core/file.py:10] - TODO: reflected reference should be ignored\n",
  next: Add or improve tests, then record updated test metrics
