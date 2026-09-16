import os
import pandas as pd
from pathlib import Path

def convert_parquet_directory(input_dir, output_dir):
    """
    Convert all parquet files in input directory to CSV format.
    Creates corresponding CSV files with same names (minus extension).
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Process each file in input directory
    for filename in os.listdir(input_dir):
        filepath = os.path.join(input_dir, filename)
        if os.path.isfile(filepath) and filename.lower().endswith('.parquet'):
            print(f"Processing {filename}...")

            try:
                # Read parquet file
                df = pd.read_parquet(filepath)

                # Create output CSV path (same name but .csv extension)
                csv_filename = os.path.splitext(filename)[0] + '.csv'
                csv_path = os.path.join(output_dir, csv_filename)

                # Write to CSV
                df.to_csv(csv_path, index=False)
                print(f"Successfully converted {filename} to {csv_filename}")

            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                continue

if __name__ == "__main__":
    # Set your input and output directories here
    input_parquet_dir = r"E:\codex-2m-thinking\Codex Data Parquets"
    output_csv_dir = r"E:\codex-2m-thinking\Converted CSVs"

    convert_parquet_directory(input_parquet_dir, output_csv_dir)
    print("Conversion complete!")