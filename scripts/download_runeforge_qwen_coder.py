from __future__ import annotations

import os

from huggingface_hub import snapshot_download


def main() -> None:
    repo = os.environ["RUNEFORGE_SETUP_MODEL_REPO"]
    target = os.environ["RUNEFORGE_SETUP_MODEL_DIR"]
    snapshot_download(repo_id=repo, local_dir=target)
    print(f"snapshot ready: {target}")


if __name__ == "__main__":
    main()
