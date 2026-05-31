import duckdb
import os
import pandas as pd
import json

def write_output(df, fmt, output_dir):
    """Write the final dataset in the specified format."""
    out = os.path.join(output_dir, f"final.{fmt}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Remove any existing file to ensure clean output
    if os.path.exists(out):
        os.remove(out)

    if fmt == "csv":
        df.to_csv(out, index=False)
    elif fmt == "parquet":
        # Use pandas for better compatibility
        df.to_parquet(out)
    elif fmt == "jsonl":
        df.to_json(out, orient="records", lines=True)
    else:
        raise ValueError(f"Unsupported format: {fmt}")

def write_mlnet_format(df, output_dir, format_config=None):
    """Write dataset in ML.NET QnA format with optional customization."""
    out = os.path.join(output_dir, "mlnet_dataset.jsonl")

    # Remove any existing file to ensure clean output
    if os.path.exists(out):
        os.remove(out)

    # Default ML.NET format
    default_format = {
        "question": {"name": "Question", "type": "string"},
        "context": {"name": "Context", "type": "string"},
        "answer": {"name": "Answer", "type": "string"},
        "answer_index": {"name": "AnswerStartPosition", "type": "int"}
    }

    # Use custom format if provided, otherwise use defaults
    column_mapping = format_config if format_config else default_format

    # Create output with proper ML.NET structure
    records = []
    for _, row in df.iterrows():
        record = {}
        for col, config in column_mapping.items():
            value = row.get(col)
            if pd.isna(value):
                continue  # Skip missing values

            # Convert answer_index to int if it's a float
            if col == "answer_index" and isinstance(value, float):
                value = int(value)

            record[config["name"]] = str(value) if config["type"] == "string" else value
        records.append(record)

    with open(out, 'w', encoding='utf8') as f:
        for record in records:
            f.write(f"{json.dumps(record)}\n")