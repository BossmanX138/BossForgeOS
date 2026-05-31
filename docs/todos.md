# Open Todos

---
## TODO List Cross-References

- [BossGate Features — Master TODO List](../core/BossGate_Features_TODO.md)
- [BossForgeOS Enterprise TODO List](../ENTERPRISE_TODO_LIST.md)
- [BossForgeOS Enterprise Roadmap](../ENTERPRISE_ROADMAP.md)

All TODOs must be kept in sync and up to date by the Archivist agent. See the BossGate master TODO for canonical cross-references and duties.

Curated by Archivist from actionable TODO/FIXME/TBD signals.

Generated: 2026-05-31 06:11:26
Total actionable: 283
General backlog: 274
Test debt: 9

## Priority Backlog

- [codemage][high] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:205 :: - Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:205 :: - Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:265 :: - Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:129 :: TODO_PATTERNS = ["TODO", "FIXME", "TBD"]
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:537 :: if stripped.lower() in {"todo", "fixme", "tbd", "## todo", "# todo"}:
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:550 :: # Keep explicit TODO/FIXME markers as actionable by default.
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:551 :: if re.search(r"\b(todo|fixme|tbd)\b", lower):
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:559 :: if "fixme" in lower or any(k in lower for k in ["security", "crash", "critical", "data loss"]):
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:638 :: "Curated by Archivist from actionable TODO/FIXME/TBD signals.",
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:700 :: "- Regularly scan all TODO lists and codebase for actionable TODO/FIXME/TBD/test debt items.",
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\agents\codemage_agent.py:654 :: todo_hits = [line.strip() for line in lines if "TODO" in line.upper() or "FIXME" in line.upper()][:10]
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\core\rune\discovery_handoff.py:20 :: TODO_LINE_RE = re.compile(r"\b(?:TODO|FIXME|TBD)\b", re.IGNORECASE)
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\modules\runeforge_provider\models\runeforge-mk0-7b\tokenizer.json:34651 :: "▁FIXME": 27610,
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\modules\runeforge_provider\models\runeforge-mk0-7b\checkpoint-2000\tokenizer.json:34651 :: "▁FIXME": 27610,
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\modules\runeforge_provider\models\runeforge-mk0-7b\checkpoint-2500\tokenizer.json:34651 :: "▁FIXME": 27610,
  next: Create fix plan, implement patch, and add regression tests
- [codemage][high] F:\Bosscrafts\BossForgeOS\modules\runeforge_provider\models\Runeforge_Alpha-7b\tokenizer.json:34651 :: "▁FIXME": 27610,
  next: Create fix plan, implement patch, and add regression tests
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:206 :: - Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:208 :: - When a TODO is completed, update all lists and remove or archive the item.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:209 :: - If a TODO is moved, merged, or split, update all references and cross-links.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:210 :: - ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decrees
  next: Convert this note into a tracked work item with owner/date
- [codemage][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:5 :: Each TODO is staged for agent delegation. Agents can be assigned to design, implement, test, or document each item as discrete tasks.
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:206 :: - Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:208 :: - When a TODO is completed, update all lists and remove or archive the item.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:209 :: - If a TODO is moved, merged, or split, update all references and cross-links.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_TODO_LIST.md:210 :: - ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decrees
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\.github\copilot-instructions.md:2 :: Verify that the copilot-instructions.md file in the .github directory is created.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\.github\copilot-instructions.md:36 :: Create and Run Task
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\.github\copilot-instructions.md:49 :: Ensure Documentation is Complete
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossCrafts_Devlot_MkII.md:49 :: - Documents completed work and updates TODO lists.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossCrafts_Devlot_MkII.md:52 :: - If no one responds to his suggestions via the bus within a reasonable time, he will append his suggestions directly to the TODO item he just cleared, clearly stating that Devlot completed the task and these are suggestions (not new TODOs 
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Auth_stubs.py:67 :: # TODO: Implement biometric/password/other verification
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:9 :: Design and implement Prime BossGate UI (messenger, file transfer, voice chat, address book, status)
  next: Review context, confirm scope, and create a concrete next task
- [archivist][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:10 :: Integrate address ledger and presence/status indicators
  next: Update documentation section and cross-link related docs
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:14 :: Implement TLS 1.3+ mutual authentication for all encrypted comms
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:31 :: Privacy boundaries for foreign addresses
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:35 :: Enforce 7-word, asterisk-wrapped address format
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:36 :: Cryptographically secure address generation
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:39 :: Implement skill checks for agents, role checks for humans
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:266 :: - Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:268 :: - When a TODO is completed, update all lists and remove or archive the item.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:269 :: - If a TODO is moved, merged, or split, update all references and cross-links.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Features_TODO.md:270 :: - ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decrees
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\BossGate_Prime_Tab_stubs.py:65 :: # TODO: Add video chat, group chat, collaborative editing, etc.
  next: Convert this note into a tracked work item with owner/date
- [codemage][medium] F:\Bosscrafts\BossForgeOS\core\ENTERPRISE_TODO_LIST.md:19 :: Implement full agent memory, social dynamics, refusal, and retirement logic in code.
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\ENTERPRISE_TODO_LIST.md:20 :: Scaffold or implement real scripts/programs for each sigil’s function as needed.
  next: Review context, confirm scope, and create a concrete next task
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\ENTERPRISE_TODO_LIST.md:22 :: Maintain and update Decrees_and_Governance.md with every new decree.
  next: Review context, confirm scope, and create a concrete next task
- [codemage][medium] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:194 :: "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
  next: Open implementation task with acceptance criteria and tests
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:676 :: # --- Cross-link and update all major TODO lists ---
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:701 :: "- Update this master TODO to reference all other lists and ensure all items are current and not duplicated or orphaned.",
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:703 :: "- When a TODO is completed, update all lists and remove or archive the item.",
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:704 :: "- If a TODO is moved, merged, or split, update all references and cross-links.",
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:705 :: "- ENFORCEMENT DECREE: All user decrees must be recorded in TODO files or roadmaps. The Archivist must synchronize decrees across all documentation. See [../../Decrees_and_Governance.md](../../Decrees_and_Governance.md) for canonical decree
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\agents\archivist_agent.py:711 :: # List of major TODO files to update
  next: Convert this note into a tracked work item with owner/date
- [codemage][medium] F:\Bosscrafts\BossForgeOS\core\agents\master_agents.py:17 :: "description": "Project archivist, TODO/test debt scanner, and documentation agent.",
  next: Open implementation task with acceptance criteria and tests
- [archivist][medium] F:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:280 :: # TODO: Implement AES-256-GCM encryption/decryption for ledger files.
  next: Update documentation section and cross-link related docs
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:283 :: # TODO: Use os.urandom or secrets module for cryptographically secure address generation.
  next: Convert this note into a tracked work item with owner/date
- [archivist][medium] F:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:284 :: # TODO: Add HMAC or digital signature to each ledger entry for tamper-evidence.
  next: Update documentation section and cross-link related docs
- [devlot][medium] F:\Bosscrafts\BossForgeOS\core\connectors\bossgate_connector.py:285 :: # TODO: Implement secure deletion (e.g., file shredding) for retired addresses/keys.
  next: Convert this note into a tracked work item with owner/date
- [archivist][medium] F:\Bosscrafts\BossForgeOS\docs\autonomous_work_session.md:14 :: - Implemented policy TODO batch in `docs/AgentForge_readme.md`:
  next: Update documentation section and cross-link related docs
- [devlot][medium] F:\Bosscrafts\BossForgeOS\docs\progress_report_2026-04-04.md:6 :: - Progress will be updated in this log and in the main todo list as agents complete their work.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\m365_copilot_connector\README.md:38 :: - Added extension hook: `DevlotAutonomyHooks` for TODO automation and recommendation events.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:9 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:13 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:17 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:21 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:25 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:29 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:33 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:37 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:41 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:45 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:49 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:53 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:57 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:61 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:65 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:69 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:73 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:77 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date
- [devlot][medium] F:\Bosscrafts\BossForgeOS\ENTERPRISE_ROADMAP.md:81 :: The Archivist is responsible for TODO list hygiene, decree enforcement, and cross-repo accuracy.
  next: Convert this note into a tracked work item with owner/date

## Test Debt

- [test_sentinel][high] F:\Bosscrafts\BossForgeOS\core\agents\test_sentinel_agent.py:177 :: pattern = re.compile(r"TODO|FIXME|TBD", re.IGNORECASE)
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][high] F:\Bosscrafts\BossForgeOS\core\agents\test_sentinel_agent.py:196 :: "severity": "high" if "fixme" in line.lower() else "medium",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] F:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:119 :: (project / "notes.txt").write_text("todo\n", encoding="utf-8")
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] F:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:295 :: "# TODO: implement archival retention policy\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] F:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:329 :: "# TODO: implement command routing\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] F:\Bosscrafts\BossForgeOS\tests\test_codemage_agent.py:31 :: "args": {"language": "python", "content": "print('x')\n# TODO: improve"},
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] F:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:248 :: "# TODO: real work item\n",
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] F:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:255 :: self.assertIn("TODO: real work item", str(todos[0].get("text", "")))
  next: Add or improve tests, then record updated test metrics
- [test_sentinel][medium] F:\Bosscrafts\BossForgeOS\tests\test_archivist_agent.py:291 :: "- [core/file.py:10] - TODO: reflected reference should be ignored\n",
  next: Add or improve tests, then record updated test metrics
