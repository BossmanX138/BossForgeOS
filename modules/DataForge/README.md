# DataForge - BossForgeOS Core Module

DataForge is the official BossForgeOS data-smithing subsystem.

## Table of Contents

- [Capabilities](#capabilities)
- [CLI Example](#cli-example)

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
