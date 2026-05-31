# Module Doctor Runbook

## Purpose
`bforge module doctor` is the standard quick health check for module registry, runtime tracking, and smoke execution.

## Commands

Base check:

```powershell
bforge module doctor
```

Extended check (includes non `python -m` entrypoints):

```powershell
bforge module doctor --include-external
```

Fallback if `bforge` is not in PATH:

```powershell
C:\Users\Bossm\BossCrafts\bin\bforge.cmd module doctor
```

## Expected Output
- `ok: true`
- `validation.ok: true`
- `runtime.modules`: list with `pid`, `running`, `started_at`
- `smoke.ok: true` for successful smoke checks
- `status: skipped` for non-`python -m` modules unless `--include-external` is passed

## Failure Triage
1. `validation.ok: false`
- Fix invalid/missing `manifest.json` fields.

2. `smoke.ok: false`
- Re-run specific module standalone command manually with `--once`.
- Check module dependencies in active Python environment.

3. Runtime entries stale (`running: false` with non-zero pid)
- Run `bforge module stop <module_id>` to clear stale state.

4. `bforge` command not found
- Open a new terminal after install, or run the explicit shim path:
  - `C:\Users\Bossm\BossCrafts\bin\bforge.cmd`
