"""Combine same-schema Parquet shards into a new CSV using PyArrow."""
if __package__:
    from .parquet_cli import fresh_csv, parquet_sources, read_only_destination, run_cli
else:
    from parquet_cli import fresh_csv, parquet_sources, read_only_destination, run_cli


def combine_with_pyarrow(input_dir, output_file):
    """Append shards by rows, preserving the common Arrow schema."""
    import pyarrow as pa
    import pyarrow.csv as csv
    import pyarrow.parquet as pq

    root, files = parquet_sources(input_dir)
    out = fresh_csv(read_only_destination(root, output_file))
    table = pa.concat_tables([pq.read_table(part) for part in files])
    with out.open("xb") as file:
        csv.write_csv(table, file)
    print(f"Combined {len(files)} Parquet files into {out}")


def main(argv=None):
    return run_cli(combine_with_pyarrow, "--output-file", __doc__, argv)


if __name__ == "__main__":
    raise SystemExit(main())
