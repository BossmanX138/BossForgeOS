# BossForgeOS Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real Windows installer artifact named `Install BossForge_OS.exe` that installs a runnable `BossForgeOS.exe` from the current repository state.

**Architecture:** Use PyInstaller for both layers so the build works with tools already available in this workspace. First, build a portable `BossForgeOS.exe` from `launcher/bossforge_launcher.py`; then create a single-file installer executable that carries a zipped release payload, extracts it into a chosen install directory, writes shortcuts, and records a release manifest under `releases/`.

**Tech Stack:** Python, PyInstaller, PowerShell-friendly Windows filesystem/shortcut behavior, JSON release manifests

---

### Task 1: Add installer payload and release-build helpers

**Files:**
- Create: `installer/build_release_payload.py`
- Create: `installer/install_bossforge_os.py`
- Create: `installer/installer_readme.md`
- Test: `tests/test_installer_payload.py`

- [ ] **Step 1: Write the failing payload test**

```python
from pathlib import Path

from installer.build_release_payload import build_payload_manifest


def test_build_payload_manifest_includes_launcher_and_assets(tmp_path: Path) -> None:
    manifest = build_payload_manifest(project_root=tmp_path)
    include_roots = {entry["path"] for entry in manifest["include"]}
    assert "assets" in include_roots
    assert "launcher" in include_roots
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_installer_payload.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing `build_payload_manifest`

- [ ] **Step 3: Write the minimal payload builder**

```python
def build_payload_manifest(project_root: Path) -> dict[str, object]:
    return {
        "include": [
            {"path": "assets", "kind": "dir"},
            {"path": "launcher", "kind": "dir"},
            {"path": "core", "kind": "dir"},
            {"path": "ui", "kind": "dir"},
        ]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_installer_payload.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add installer/build_release_payload.py installer/install_bossforge_os.py installer/installer_readme.md tests/test_installer_payload.py
git commit -m "feat: add BossForgeOS installer payload helpers"
```

### Task 2: Build the packaged BossForgeOS launcher and installer executables

**Files:**
- Create: `installer/BossForgeOS.spec`
- Create: `installer/Install_BossForge_OS.spec`
- Create: `scripts/build_bossforge_installer.ps1`
- Modify: `releases/releases_readme.md`
- Test: `tests/test_installer_payload.py`

- [ ] **Step 1: Write the failing build-script test**

```python
from pathlib import Path


def test_build_script_exists() -> None:
    assert Path("scripts/build_bossforge_installer.ps1").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_installer_payload.py -q`
Expected: FAIL because the build script does not exist yet

- [ ] **Step 3: Write the minimal build pipeline**

```powershell
python -m PyInstaller installer\BossForgeOS.spec --noconfirm
python installer\build_release_payload.py
python -m PyInstaller installer\Install_BossForge_OS.spec --noconfirm
```

- [ ] **Step 4: Run tests and a local build**

Run: `python -m pytest tests/test_installer_payload.py -q`
Expected: PASS

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_bossforge_installer.ps1`
Expected: produces `releases/latest/Install BossForge_OS.exe`

- [ ] **Step 5: Commit**

```bash
git add installer/BossForgeOS.spec installer/Install_BossForge_OS.spec scripts/build_bossforge_installer.ps1 releases/releases_readme.md
git commit -m "feat: add BossForgeOS installer build pipeline"
```

### Task 3: Stamp release metadata and archive prior launcher-era artifacts

**Files:**
- Modify: `installer/build_release_payload.py`
- Modify: `scripts/build_bossforge_installer.ps1`
- Modify: `releases/latest/release_manifest.json`
- Create: `releases/archive/`
- Test: `tests/test_installer_payload.py`

- [ ] **Step 1: Write the failing manifest test**

```python
from installer.build_release_payload import build_release_manifest


def test_release_manifest_uses_bossforgeos_installer_name() -> None:
    manifest = build_release_manifest("abc123", "Install BossForge_OS.exe")
    assert manifest["artifactName"] == "Install BossForge_OS.exe"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_installer_payload.py -q`
Expected: FAIL because `build_release_manifest` does not exist

- [ ] **Step 3: Add manifest/archive handling**

```python
def build_release_manifest(source_commit: str, artifact_name: str) -> dict[str, str]:
    return {
        "product": "BossForgeOS",
        "artifactName": artifact_name,
        "sourceCommit": source_commit,
    }
```

- [ ] **Step 4: Run tests and rebuild artifacts**

Run: `python -m pytest tests/test_installer_payload.py -q`
Expected: PASS

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_bossforge_installer.ps1`
Expected: PASS with archived launcher-era files and a fresh installer manifest

- [ ] **Step 5: Commit**

```bash
git add installer/build_release_payload.py scripts/build_bossforge_installer.ps1 releases
git commit -m "feat: stamp BossForgeOS installer releases"
```
