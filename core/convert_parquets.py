"""Compatibility entry point for the standalone DataForge converter."""
if not __package__:
    import sys
    from pathlib import Path

    # Direct invocation sets sys.path[0] to core/, not this repository root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.DataForge.convert_parquets import convert_parquet_directory, main

__all__ = ["convert_parquet_directory", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
