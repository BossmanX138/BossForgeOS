"""Shared path and command-line contract for the standalone parquet tools."""
import argparse
from pathlib import Path


def parquet_sources(input_dir):
    root = Path(input_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Input directory does not exist: {root}")
    files = sorted(
        (p for p in root.iterdir() if p.is_file() and p.suffix.casefold() == ".parquet"),
        key=lambda p: (p.name.casefold(), p.name),
    )
    if not files:
        raise ValueError(f"No Parquet files found in: {root}")
    return root, files


def read_only_destination(root, output):
    dest = Path(output).resolve()
    if dest == root or root in dest.parents:
        raise ValueError(f"Output must be outside the read-only input directory: {dest}")
    return dest


def fresh_csv(path):
    if path.suffix.casefold() != ".csv":
        raise ValueError(f"Output filename must end in .csv: {path}")
    if path.exists() or path.is_symlink():
        raise ValueError(f"Refusing to overwrite existing output: {path}")
    return path


def run_cli(action, output_option, description, argv=None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input-dir", required=True, type=Path,
                        help="Existing Parquet directory (read-only)")
    parser.add_argument(output_option, required=True, type=Path,
                        help="Explicit CSV destination outside the input directory")
    args = parser.parse_args(argv)
    try:
        action(args.input_dir, getattr(args, output_option[2:].replace("-", "_")))
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    return 0
