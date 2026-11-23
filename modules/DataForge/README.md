# DataForge - BossForgeOS Core Module

DataForge is the official BossForgeOS data-smithing subsystem.

## Table of Contents

- [Capabilities](#capabilities)
- [CLI Example](#cli-example)
- [Standalone Parquet exports](#standalone-parquet-exports)

## Capabilities
- Load dataset formats (parquet, jsonl, json, csv, yaml)
- Inspect schema
- Validate rows
- Auto-repair broken data
- Batch process shards
- Merge datasets
- Output to multiple formats

## CLI Example
`bforge run dataforge --input shards/ --output clean/ --format parquet`

## Standalone Parquet exports

Run these from the BossForgeOS root with pandas and PyArrow installed in your
project environment. Both source and destination are required. No helper
selects a drive or writes to the current directory implicitly.

    python -m modules.DataForge.convert_parquets --input-dir "data/raw shards" --output-dir "exports/shard CSVs"
    python -m modules.DataForge.combine_parquets --input-dir "data/raw shards" --output-file "exports/combined.csv"
    python -m modules.DataForge.combine_parquets_pyarrow --input-dir "data/raw shards" --output-file "exports/combined-arrow.csv"

The legacy core/convert_parquets.py path accepts the same converter flags.
Create the parent directory for a combined CSV before you run a combiner.

Treat the input directory as read-only. Use a project-owned dataset or an
explicitly approved shared dataset, and select a project-local or
user-designated writable output location outside the input. Existing CSVs
are not overwritten; choose a fresh output path. These are batch utilities:
if conversion fails partway through, review any files already exported before
retrying into a fresh destination.

Both combiners append rows in filename order. The PyArrow combiner requires
the same schema in each shard. The pandas combiner aligns columns by name.
