import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_DIR_NAME = "Anvil Secured Shuttle (A.S.S.)"


def _is_ass_directory(path: Path) -> bool:
    required = ["package.json", "electron-main.js", "index.html", "assets"]
    return all((path / entry).exists() for entry in required)


def _resolve_ass_dir() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates: list[Path] = []

    env_candidate = os.environ.get("BOSSFORGE_ASS_DIR", "").strip()
    if env_candidate:
        candidates.append(Path(env_candidate).expanduser())

    candidates.extend(
        [
            script_dir / APP_DIR_NAME,
            script_dir.parent / APP_DIR_NAME,
            Path.cwd() / APP_DIR_NAME,
            Path.cwd(),
        ]
    )

    for candidate in candidates:
        resolved = candidate.resolve()
        if _is_ass_directory(resolved):
            return resolved
    return None


def _resolve_electron_bin(ass_dir: Path) -> str:
    local_bins = [
        ass_dir / "node_modules" / ".bin" / "electron.cmd",
        ass_dir / "node_modules" / ".bin" / "electron.exe",
        ass_dir / "node_modules" / ".bin" / "electron",
    ]
    for candidate in local_bins:
        if candidate.exists():
            return str(candidate)

    global_electron = shutil.which("electron")
    if global_electron:
        return global_electron

    raise FileNotFoundError(
        "Electron binary not found. Install dependencies in A.S.S. (npm install) "
        "or set PATH/BOSSFORGE_ASS_DIR correctly."
    )


def main() -> int:
    ass_dir = _resolve_ass_dir()
    if ass_dir is None:
        print(
            "Failed to launch Anvil Secured Shuttle: app directory not found. "
            f"Expected '{APP_DIR_NAME}' near BossForgeOS or set BOSSFORGE_ASS_DIR."
        )
        return 1

    try:
        electron_bin = _resolve_electron_bin(ass_dir)
        subprocess.Popen([electron_bin, "."], cwd=str(ass_dir))
        print(f"Anvil Secured Shuttle launched from: {ass_dir}")
        return 0
    except Exception as exc:
        print(f"Failed to launch Anvil Secured Shuttle: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
