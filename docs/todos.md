# Open Todos

---
## TODO List Cross-References

- [BossGate Features — Master TODO List](../core/BossGate_Features_TODO.md)
- [BossForgeOS Enterprise TODO List](../ENTERPRISE_TODO_LIST.md)
- [BossForgeOS Enterprise Roadmap](../ENTERPRISE_ROADMAP.md)

All TODOs must be kept in sync and up to date by the Archivist agent. See the BossGate master TODO for canonical cross-references and duties.

Curated by Archivist from actionable TODO/FIXME/TBD signals.

Generated: 2026-06-12 23:29:15
Total actionable: 485
General backlog: 472
Test debt: 13

## Priority Backlog

- [codemage][high] I:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:97 :: - Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:625 :: - Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:681 :: - Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:134 :: TODO_PATTERNS = ["TODO", "FIXME", "TBD"]
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:559 :: if stripped.lower() in {"todo", "fixme", "tbd", "## todo", "# todo"}:
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:572 :: # Keep explicit TODO/FIXME markers as actionable by default.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:573 :: if re.search(r"\b(todo|fixme|tbd)\b", lower):
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:581 :: if "fixme" in lower or any(k in lower for k in ["security", "crash", "critical", "data loss"]):
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:660 :: "Curated by Archivist from actionable TODO/FIXME/TBD signals.",
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:722 :: "- Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.",
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\agents\codemage_agent.py:716 :: todo_hits = [line.strip() for line in lines if "TODO" in line.upper() or "FIXME" in line.upper()][:10]
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] I:\Bosscrafts\BossForgeOS\core\rune\discovery_handoff.py:20 :: TODO_LINE_RE = re.compile(r"\b(?:TODO|FIXME|TBD)\b", re.IGNORECASE)
  next: Create fix plan, implement patch, and add regression tests
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:98 :: - Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:100 :: - When a TODO is completed, update all lists and remove or archive the item.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:101 :: - If a TODO is moved, merged, or split, update all references and cross-links.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:102 :: - ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decrees
  next: Convert this note into a tracked work item with owner/date
- [codemage][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:5 :: Each TODO is staged for agent delegation. Agents can be assigned to design, implement, test, or document each item as discrete tasks.
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:626 :: - Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:628 :: - When a TODO is completed, update all lists and remove or archive the item.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:629 :: - If a TODO is moved, merged, or split, update all references and cross-links.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:630 :: - ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decrees
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\.github\copilot-instructions.md:2 :: Verify that the copilot-instructions.md file in the .github directory is created.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\.github\copilot-instructions.md:36 :: Create and Run Task
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\.github\copilot-instructions.md:49 :: Ensure Documentation is Complete
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossCrafts_Devlot_MkII.md:49 :: - Documents completed work and updates TODO lists.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossCrafts_Devlot_MkII.md:52 :: - If no one responds to his suggestions via the bus within a reasonable time, he will append his suggestions directly to the TODO item he just cleared, clearly stating that Devlot completed the task and these are suggestions (not new TODOs 
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Auth_stubs.py:67 :: # TODO: Implement biometric/password/other verification
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:9 :: Design and implement Prime BossGate UI (messenger, file transfer, voice chat, address book, status)
  next: Review context, confirm scope, and create a concrete next task
- [archivist][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:10 :: Integrate address ledger and presence/status indicators
  next: Update documentation section and cross-link related docs
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:14 :: Implement TLS 1.3+ mutual authentication for all encrypted comms
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:31 :: Privacy boundaries for foreign addresses
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:35 :: Enforce 7-word, asterisk-wrapped address format
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:36 :: Cryptographically secure address generation
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:39 :: Implement skill checks for agents, role checks for humans
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:682 :: - Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:684 :: - When a TODO is completed, update all lists and remove or archive the item.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:685 :: - If a TODO is moved, merged, or split, update all references and cross-links.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:686 :: - ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decrees
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\BossGate_Prime_Tab_stubs.py:65 :: # TODO: Add video chat, group chat, collaborative editing, etc.
  next: Convert this note into a tracked work item with owner/date
- [codemage][medium] I:\Bosscrafts\BossForgeOS\core\ENTERPRISE_TODO_LIST.md:19 :: Implement full agent memory, social dynamics, refusal, and retirement logic in code.
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\ENTERPRISE_TODO_LIST.md:20 :: Scaffold or implement real scripts/programs for each sigil’s function as needed.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\ENTERPRISE_TODO_LIST.md:22 :: Maintain and update Decrees_and_Governance.md with every new decree.
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:199 :: "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:698 :: # --- Cross-link and update all major TODO lists ---
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:723 :: "- Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.",
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:725 :: "- When a TODO is completed, update all lists and remove or archive the item.",
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:726 :: "- If a TODO is moved, merged, or split, update all references and cross-links.",
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:727 :: "- ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decree
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:733 :: # List of major TODO files to update
  next: Convert this note into a tracked work item with owner/date
- [codemage][medium] I:\Bosscrafts\BossForgeOS\core\agents\master_agents.py:17 :: "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
  next: Open implementation task with acceptance criteria and tests
- [archivist][medium] I:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:585 :: # TODO: Implement AES-256-GCM encryption/decryption for ledger files.
  next: Update documentation section and cross-link related docs
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:588 :: # TODO: Use os.urandom or secrets module for cryptographically secure address generation.
  next: Convert this note into a tracked work item with owner/date
- [archivist][medium] I:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:589 :: # TODO: Add HMAC or digital signature to each ledger entry for tamper-evidence.
  next: Update documentation section and cross-link related docs
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:590 :: # TODO: Implement secure deletion (e.g., file shredding) for retired addresses/keys.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\utils\bforge.py:1423 :: p_bg_complete = p_bossgate_sub.add_parser("complete", help="Mark a BossGate TODO id as completed")
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] I:\Bosscrafts\BossForgeOS\core\utils\bforge.py:1424 :: p_bg_complete.add_argument("todo_id", help="Todo id, e.g. BG-004")
  next: Convert this note into a tracked work item with owner/date
- [archivist][medium] I:\Bosscrafts\BossForgeOS\docs\autonomous_work_session.md:14 :: - Implemented policy TODO batch in `docs/AgentForge_readme.md`:
  next: Update documentation section and cross-link related docs
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:25 :: Store encrypted private memory and relationship records inside the capsule.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:26 :: Add memory-first learning inputs without exposing private records through public views.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:31 :: Validate signed checkpoints before activation.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:36 :: Add empty-slot and class/type constraints for skill learning between consenting agents.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:37 :: Add Forge, dead-agent recovery, and consenting live-agent trade rules for tools.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:38 :: Add signed-lineage sigil evolution while preserving explicit promotion-only rank and immutable rarity.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:42 :: Move the complete encrypted capsule rather than copying it.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossforge_ai_runner_todo.md:43 :: Restrict address enumeration to Prime BossGates at BossForgeOS, A.S.S., and Bridgebase Alpha.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:15 :: (BG-002) Add protocol version table (`v1-prototype`, `v1-pilot`) and compatibility notes.
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:16 :: (BG-003) Add a command-to-test mapping section for all BossGate commands.
  next: Open implementation task with acceptance criteria and tests
- [codemage][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:39 :: (BG-012) Add explicit deny reason codes to all blocked operations.
  next: Open implementation task with acceptance criteria and tests
- [archivist][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:44 :: (BG-014) Add immutable/auditable transfer ledger format with correlation ids.
  next: Update documentation section and cross-link related docs
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:45 :: (BG-015) Implement `bossgate_usage_report` command with local aggregation.
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:46 :: (BG-016) Add telemetry tests for event completeness per flow.
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:50 :: (BG-017) Implement `bossgate_license_issue`.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:51 :: (BG-018) Implement `bossgate_license_validate`.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:53 :: (BG-020) Implement revocation checks and denial paths.
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:58 :: (BG-022) Implement `bossgate_remote_debug_open` with time-bound scoped session tokens.
  next: Open implementation task with acceptance criteria and tests
- [codemage][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:59 :: (BG-023) Implement `bossgate_remote_debug_close` and emergency revoke/kill switch.
  next: Open implementation task with acceptance criteria and tests
- [codemage][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:61 :: (BG-025) Add tests for token expiry and out-of-scope command rejection.
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:65 :: (BG-026) Build interface map from discovery and scan outputs.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:67 :: (BG-028) Require explicit approval for write/destructive connector operations.
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] I:\Bosscrafts\BossForgeOS\docs\bossgate_connector_todo.md:68 :: (BG-029) Add one end-to-end generation test for an approved sample target.
  next: Open implementation task with acceptance criteria and tests

## Test Debt

- [test_sentinel][high] I:\Bosscrafts\BossForgeOS\core\agents\test_sentinel_agent.py:177 :: pattern = re.compile(r"TODO|FIXME|TBD", re.IGNORECASE)
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][high] I:\Bosscrafts\BossForgeOS\core\agents\test_sentinel_agent.py:196 :: "severity": "high" if "fixme" in line.lower() else "medium",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][high] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:356 :: '{"token":"FIXME"}\n',
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:119 :: (project / "notes.txt").write_text("todo\n", encoding="utf-8")
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:295 :: "# TODO: implement archival retention policy\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:344 :: "# TODO: implement real backlog task\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:352 :: "## TODO\n\n- [ ] Implement plan step placeholder\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:395 :: "# TODO: implement command routing\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_codemage_agent.py:31 :: "args": {"language": "python", "content": "print('x')\n# TODO: improve"},
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:248 :: "# TODO: real work item\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:255 :: self.assertIn("TODO: real work item", str(todos[0].get("text", "")))
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:291 :: "- [core/file.py:10] - TODO: reflected reference should be ignored\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] I:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:348 :: "# TODO: copied worktree task should be ignored\n",
  next: Add or improve tests, then record updated test metrics
