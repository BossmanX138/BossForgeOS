# Backlog Triage And Todo Noise Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a trustworthy BossForgeOS backlog by removing self-generated TODO scanner noise first, then use the cleaned backlog to drive the highest-value completion work.

**Architecture:** Treat backlog quality as a prerequisite system. Tighten `ArchivistAgent` TODO collection so it ignores mirrored worktrees, generated Superpowers planning/spec content, and model artifact directories, while preserving real source TODOs and test debt. After the scanner is trustworthy, use the reduced actionable set to sequence the next completion slices by operational risk and user-facing leverage.

**Tech Stack:** Python 3, `unittest`, ArchivistAgent policy/state JSON, local filesystem scanning.

---

## Finish-By-Importance Order

1. **Backlog trust restoration**
   - Fix Archivist TODO scanner noise so `docs/todos.md` stops overcounting worktree copies, generated plan/spec docs, and model artifact tokens.
   - Why first: all broader prioritization is distorted until this is fixed.
2. **BossGate security hardening gaps**
   - Finish explicit deny reason codes, key/ledger hardening, and remaining auth/security TODOs.
   - Why second: this is the highest-risk unfinished subsystem in the repo.
3. **BossGate telemetry and auditable lifecycle coverage**
   - Implement canonical correlated events, usage reporting, and transfer/session audit completeness.
   - Why third: the transport exists, but enterprise-grade visibility is still incomplete.
4. **Control Hall and operational workflow polish**
   - Keep landing dashboard/decision flows tight and fill missing orchestration/operator affordances.
   - Why fourth: this is the primary surface the user sees and uses.
5. **VS Code extension completion**
   - Move from command-adapter state toward sidebar/event-stream/response-panel usefulness.
   - Why fifth: valuable, but less critical than securing and stabilizing the core runtime.
6. **ForgeShell and advanced orchestration**
   - Expand the shell and distributed/cloud orchestration after the backlog, security, and operator surface are dependable.
   - Why sixth: useful power features, but not the first blocker to finishing the platform.

## File Map

Modify:

- `core/agents/archivist_agent.py`
  - TODO ignore defaults
  - policy merge behavior
  - explicit generated-plan/spec path suppression
- `tests/test_archivist_agent.py`
  - regression coverage for worktree/plan/model noise
  - regression coverage for persisted policy merges preserving new default ignores

Read for prioritization context:

- `docs/todos.md`
- `docs/bossgate_connector_todo.md`
- `core/BossGate_Features_TODO.md`
- `extension/README.md`

### Task 1: Remove TODO Scanner Noise From Mirrored And Generated Sources

**Files:**
- Modify: `core/agents/archivist_agent.py`
- Modify: `tests/test_archivist_agent.py`

- [x] **Step 1: Write the failing regression for worktree, plan, and model noise**

```python
def test_collect_todos_skips_worktree_plan_and_model_noise(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        project = root / "project_noise_sources"
        src = project / "src"
        worktree = project / ".worktrees" / "feature-copy" / "src"
        plans = project / "docs" / "superpowers" / "plans"
        model_dir = (
            project
            / "modules"
            / "runeforge_provider"
            / "models"
            / "Runeforge_Alpha-7b"
        )

        src.mkdir(parents=True)
        worktree.mkdir(parents=True)
        plans.mkdir(parents=True)
        model_dir.mkdir(parents=True)

        (src / "real_work.py").write_text(
            "# TODO: implement real backlog task\n",
            encoding="utf-8",
        )
        (worktree / "copy.py").write_text(
            "# TODO: copied worktree task should be ignored\n",
            encoding="utf-8",
        )
        (plans / "2026-06-12-sample-plan.md").write_text(
            "## TODO\n\n- [ ] Implement plan step placeholder\n",
            encoding="utf-8",
        )
        (model_dir / "tokenizer.json").write_text(
            '{"token":"FIXME"}\n',
            encoding="utf-8",
        )

        agent = ArchivistAgent(root=root)
        todos = agent._collect_todos(project)

        self.assertEqual(len(todos), 1)
        self.assertIn("real backlog task", str(todos[0].get("text", "")).lower())
```

- [x] **Step 2: Run the regression to verify it fails**

Run:

```powershell
python -m unittest tests.test_archivist_agent.ArchivistAgentTests.test_collect_todos_skips_worktree_plan_and_model_noise -v
```

Expected: `FAIL` with `AssertionError: 4 != 1`.

- [x] **Step 3: Write the failing regression for persisted policy merges**

```python
def test_policy_keeps_new_default_todo_ignore_directories(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_dir = root / "bus" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "archivist_policy.json").write_text(
            json.dumps(
                {
                    "todo_ignore_dir_names": [".git", ".continue"],
                    "todo_scan_suffixes": [".py", ".md"],
                }
            ),
            encoding="utf-8",
        )

        agent = ArchivistAgent(root=root)
        ignore_dirs = agent._todo_ignore_dir_names()

        self.assertIn(".worktrees", ignore_dirs)
        self.assertIn(".superpowers", ignore_dirs)
        self.assertIn("models", ignore_dirs)
        self.assertIn(".git", ignore_dirs)
```

- [x] **Step 4: Run the policy regression to verify it fails**

Run:

```powershell
python -m unittest tests.test_archivist_agent.ArchivistAgentTests.test_policy_keeps_new_default_todo_ignore_directories -v
```

Expected: `FAIL` because the loaded policy only returns `{'.git', '.continue'}`.

- [x] **Step 5: Implement the minimal Archivist fix**

```python
TODO_IGNORE_DIR_NAMES = {
    ".git",
    ".continue",
    ".superpowers",
    ".venv",
    ".venv-xtts",
    ".venv-vllm",
    ".runtime",
    ".models",
    ".worktrees",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    "bus",
    "archives",
    "models",
    "releases",
}

TODO_IGNORE_GLOBS = {
    "**/.venv/**",
    "**/.venv-*/**",
    "**/node_modules/**",
    "**/site-packages/**",
    "**/docs/autonomous_todo_backlog.md",
    "**/docs/delegation_notes.md",
    "**/docs/daily_ledger.md",
    "**/docs/superpowers/plans/**",
    "**/docs/superpowers/specs/**",
}

if (
    rel_posix.startswith("docs/superpowers/plans/")
    or rel_posix.startswith("docs/superpowers/specs/")
):
    return True

additive_keys = {
    "todo_scan_suffixes",
    "todo_ignore_dir_names",
    "todo_ignore_file_names",
    "todo_ignore_globs",
    "readme_ignore_dir_names",
}
override_keys = {
    "todo_patterns",
}

for key in additive_keys:
    values = self._normalize_list(loaded.get(key))
    if not values:
        continue
    existing = self._normalize_list(default.get(key))
    merged[key] = sorted({*existing, *values})

for key in override_keys:
    values = self._normalize_list(loaded.get(key))
    if values:
        merged[key] = values
```

- [x] **Step 6: Run the Archivist suite**

Run:

```powershell
python -m unittest tests.test_archivist_agent -v
python -W error::ResourceWarning -m unittest tests.test_archivist_agent -q
```

Expected: `17` tests pass and warning-clean output.

- [x] **Step 7: Recheck live backlog noise without rewriting docs**

Run:

```powershell
@'
from pathlib import Path
from core.agents.archivist_agent import ArchivistAgent
project = Path(r'i:\Bosscrafts\BossForgeOS')
agent = ArchivistAgent(root=project)
items = agent._collect_todos(project)
worktree = sum('.worktrees' in str(item.get('file','')).lower() for item in items)
plans = sum('docs/superpowers/plans/' in str(item.get('file','')).replace('\\','/').lower() for item in items)
specs = sum('docs/superpowers/specs/' in str(item.get('file','')).replace('\\','/').lower() for item in items)
models = sum('/models/' in str(item.get('file','')).replace('\\','/').lower() for item in items)
print({'total': len(items), 'worktree_hits': worktree, 'plan_hits': plans, 'spec_hits': specs, 'model_hits': models})
'@ | python -
```

Expected:

```python
{'total': 455, 'worktree_hits': 0, 'plan_hits': 0, 'spec_hits': 0, 'model_hits': 0}
```

## Next Execution Target

After Task 1, the next inline slice should be:

1. `docs/bossgate_connector_todo.md`
   - implement `BG-012` explicit deny reason codes
2. `core/connectors/bossgate_connector.py`
   - begin replacing security-hardening TODOs with concrete enforced behavior
3. corresponding BossGate tests
   - add regression coverage before changing runtime behavior
