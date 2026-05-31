import pyarrow.parquet as pq
import pyarrow.csv as csv
import glob

def combine_with_pyarrow(input_dir, output_file):
    """Combine parquet files using PyArrow"""
    # Get all parquet files
    parquet_files = glob.glob(f"{input_dir}/*.parquet")

    if not parquet_files:
        raise ValueError("No parquet files found in directory")

    # Read first file to get schema
    table = pq.read_table(parquet_files[0])

    # Append remaining files
    for file in parquet_files[1:]:
        more_data = pq.read_table(file)
        table = table.append_columns(more_data)

    # Write to CSV
    csv.write_csv(table, output_file)
    print(f"Successfully combined {len(parquet_files)} files into {output_file}")

if __name__ == "__main__":
    input_dir = "E:\\codex-2m-thinking\\Codex Data Parquets"
    output_file = "combined_dataset.csv"

    combine_with_pyarrow(input_dir, output_file)