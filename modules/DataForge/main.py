from __future__ import annotations

from modules.runtime_common import run_module_runtime


def main() -> int:
    return run_module_runtime("dataforge", "DataForge")


if __name__ == "__main__":
    raise SystemExit(main())
