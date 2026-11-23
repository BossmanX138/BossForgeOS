"""Combine Parquet shards into a new CSV using pandas."""
if __package__:
    from .parquet_cli import fresh_csv, parquet_sources, read_only_destination, run_cli
else:
    from parquet_cli import fresh_csv, parquet_sources, read_only_destination, run_cli


def combine_parquet_to_csv(input_dir, output_file):
    """Combine shards by rows, with pandas' normal column alignment."""
    import pandas as pd

    root, files = parquet_sources(input_dir)
    out = fresh_csv(read_only_destination(root, output_file))
    frame = pd.concat([pd.read_parquet(part) for part in files], ignore_index=True)
    with out.open("x", encoding="utf-8", newline="") as file:
        frame.to_csv(file, index=False)
    print(f"Combined {len(files)} Parquet files into {out}")


def main(argv=None):
    return run_cli(combine_parquet_to_csv, "--output-file", __doc__, argv)


if __name__ == "__main__":
    raise SystemExit(main())
