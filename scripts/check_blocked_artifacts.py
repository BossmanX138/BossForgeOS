from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys


BLOCKED_PREFIXES = (
    "modules/runeforge_provider/models/",
    "modules/DataForge/ignorelogs/",
)

BLOCKED_PATTERNS = (
    ".tlog/",
    "/build_vs/",
    "/x64/",
    "/Debug/",
    "/Release/",
)

BLOCKED_SUFFIXES = (
    ".obj",
    ".exe",
    ".pdb",
)


def _candidate_files(git_range: str | None) -> list[str]:
    git_exe = os.environ.get("GIT_EXE", "").strip() or shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
    if git_range:
        out = subprocess.check_output([git_exe, "diff", "--name-only", git_range], text=True)
    else:
        out = subprocess.check_output([git_exe, "ls-files"], text=True)
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Block committing large/generated artifacts")
    parser.add_argument("--range", default=os.environ.get("GIT_CHECK_RANGE", "").strip())
    args = parser.parse_args()
    git_range = args.range or None

    blocked: list[str] = []
    for path in _candidate_files(git_range):
        if path.startswith(BLOCKED_PREFIXES):
            blocked.append(path)
            continue
        if any(pattern in path for pattern in BLOCKED_PATTERNS):
            blocked.append(path)
            continue
        if path.endswith(BLOCKED_SUFFIXES):
            blocked.append(path)

    if not blocked:
        scope = git_range if git_range else "full tree"
        print(f"Artifact guard: OK ({scope})")
        return 0

    print("Artifact guard: blocked tracked artifacts found:")
    for item in blocked[:200]:
        print(f"- {item}")
    if len(blocked) > 200:
        print(f"... and {len(blocked) - 200} more")
    print("Remove these from git tracking before merge.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
