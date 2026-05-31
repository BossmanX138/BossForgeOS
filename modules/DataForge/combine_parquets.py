import pandas as pd
import glob
from pathlib import Path

def combine_parquet_to_csv(input_dir, output_file):
    """Combine all parquet files in directory to single CSV"""
    # Get all parquet files
    parquet_files = glob.glob(f"{input_dir}/*.parquet")

    if not parquet_files:
        raise ValueError("No parquet files found in directory")

    # Read and concatenate all files
    dfs = []
    for file in parquet_files:
        df = pd.read_parquet(file)
        dfs.append(df)

    combined_df = pd.concat(dfs, ignore_index=True)

    # Write to CSV
    combined_df.to_csv(output_file, index=False)
    print(f"Successfully combined {len(parquet_files)} files into {output_file}")

if __name__ == "__main__":
    input_dir = "E:\\codex-2m-thinking\\Codex Data Parquets"
    output_file = "combined_dataset.csv"

    combine_parquet_to_csv(input_dir, output_file)