def write_output(df, fmt, output_dir, chunk_size=100000):
    """Write the final dataset in the specified format as a single file,
    with optional chunking for memory efficiency."""
    out = os.path.join(output_dir, f"final.{fmt}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if fmt == "csv":
        # Write in chunks to handle very large files
        df.to_csv(out, index=False)
    elif fmt == "parquet":
        df.to_parquet(out)
    elif fmt == "jsonl":
        with open(out, 'w', encoding='utf8') as f:
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i+chunk_size]
                chunk.to_json(f, orient="records", lines=True)
    else:
        raise ValueError(f"Unsupported format: {fmt}")