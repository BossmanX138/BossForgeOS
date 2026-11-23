"""Convert a directory of standalone Parquet shards to individual CSVs."""
if __package__:
    from .parquet_cli import fresh_csv, parquet_sources, read_only_destination, run_cli
else:
    from parquet_cli import fresh_csv, parquet_sources, read_only_destination, run_cli


def convert_parquet_directory(input_dir, output_dir):
    """Read Parquet shards, creating one new CSV for each without altering input."""
    import pandas as pd

    root, files = parquet_sources(input_dir)
    out = read_only_destination(root, output_dir)
    targets = [fresh_csv(out / part.with_suffix(".csv").name) for part in files]
    # Guard case-insensitive filesystems, and mixed-case extensions on any OS.
    if len({p.name.casefold() for p in targets}) != len(targets):
        raise ValueError("Two Parquet filenames would produce the same CSV name")
    # Do not follow a destination-directory symlink back into the input dataset.
    for target in targets:
        read_only_destination(root, target)
    out.mkdir(parents=True, exist_ok=True)
    for part, target in zip(files, targets):
        frame = pd.read_parquet(part)
        with target.open("x", encoding="utf-8", newline="") as file:
            frame.to_csv(file, index=False)
        print(f"Converted {part.name} to {target}")


def main(argv=None):
    return run_cli(convert_parquet_directory, "--output-dir", __doc__, argv)


if __name__ == "__main__":
    raise SystemExit(main())
