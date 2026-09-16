"""Convert parquet datasets into ML.NET-friendly CSV columns.

Output columns are ordered as:
answer,context,question,answer_index
"""

import argparse
import os
import re
from typing import List, Tuple

import pandas as pd

def find_parquet_files(directory: str) -> List[str]:
    """Find all parquet files in the given directory and subdirectories."""
    parquet_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.parquet'):
                parquet_files.append(os.path.join(root, file))
    return parquet_files

def load_parquet_data(files: List[str]) -> pd.DataFrame:
    """Load all parquet files into a single DataFrame."""
    dfs = []
    for file in files:
        try:
            df = pd.read_parquet(file)
            dfs.append(df)
            print(f"Loaded {file} with {len(df)} rows")
        except Exception as e:
            print(f"Error loading {file}: {str(e)}")

    if not dfs:
        raise ValueError("No valid parquet files found or could be loaded")

    return pd.concat(dfs, ignore_index=True)


def stream_convert_to_csv(parquet_files: List[str], output_path: str) -> int:
    """Convert parquet files one by one and append to a single CSV."""
    total_rows = 0
    wrote_header = False

    for idx, file in enumerate(parquet_files, start=1):
        try:
            df = pd.read_parquet(file)
            mlnet_df = convert_to_mlnet_format(df)
            mode = "w" if not wrote_header else "a"
            mlnet_df.to_csv(
                output_path,
                index=False,
                encoding="utf-8-sig",
                mode=mode,
                header=not wrote_header,
            )
            wrote_header = True
            total_rows += len(mlnet_df)
            print(f"[{idx}/{len(parquet_files)}] Wrote {len(mlnet_df)} rows from {file}")
        except Exception as e:
            print(f"[{idx}/{len(parquet_files)}] Error processing {file}: {str(e)}")

    if not wrote_header:
        raise ValueError("No data was written. All parquet files failed to process.")

    return total_rows

def split_think_and_answer(text: str) -> Tuple[str, str]:
    """Split model output into context(thinking) and final answer."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return "", ""

    s = str(text)
    match = re.search(r"<think>(.*?)</think>", s, re.IGNORECASE | re.DOTALL)
    if match:
        context = match.group(1).strip()
        answer = (s[: match.start()] + s[match.end() :]).strip()
        return context, answer
    return "", s.strip()


def strip_think_block(text: str) -> str:
    """Backward-compatible helper: remove <think>...</think> and return answer text."""
    _, answer = split_think_and_answer(text)
    return answer


def convert_to_mlnet_format(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize input schema to answer/context/question/answer_index."""
    working = df.copy()

    # Accept existing target columns or map input/output source columns.
    if "question" not in working.columns and "input" in working.columns:
        working["question"] = working["input"]
    if "answer" not in working.columns and "output" in working.columns:
        contexts, answers = zip(*(split_think_and_answer(v) for v in working["output"]))
        if "context" not in working.columns:
            # Default DataForge contract keeps context empty while stripping think blocks.
            working["context"] = ""
        working["answer"] = list(answers)

    if "question" not in working.columns:
        raise ValueError("DataFrame must contain 'question' or 'input' column")
    if "answer" not in working.columns:
        raise ValueError("DataFrame must contain 'answer' or 'output' column")

    if "context" not in working.columns:
        working["context"] = ""
    if "answer_index" not in working.columns:
        working["answer_index"] = 0

    # Ensure non-null strings for text columns.
    for col in ("answer", "context", "question"):
        working[col] = working[col].fillna("").astype(str)

    # Best-effort numeric cast for answer_index.
    working["answer_index"] = pd.to_numeric(working["answer_index"], errors="coerce").fillna(0).astype(int)

    return working[["answer", "context", "question", "answer_index"]]

def save_csv(data: pd.DataFrame, output_path: str) -> None:
    """Save DataFrame to CSV file."""
    data.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Saved {len(data)} rows to {output_path}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert parquet files into ML.NET CSV format.")
    parser.add_argument(
        "--input-directory",
        default="data/parquets",
        help="Directory containing parquet files (searched recursively).",
    )
    parser.add_argument(
        "--output-file",
        default="mlnet_training_data.csv",
        help="Output CSV file path.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_directory = args.input_directory
    output_file = args.output_file

    try:
        # Find all parquet files
        print(f"Searching for parquet files in {input_directory}...")
        parquet_files = find_parquet_files(input_directory)

        if not parquet_files:
            raise FileNotFoundError(f"No parquet files found in {input_directory}")

        print(f"Found {len(parquet_files)} parquet file(s)")

        # Stream conversion to avoid out-of-memory on large datasets
        print("Streaming parquet files into ML.NET CSV...")
        total_rows = stream_convert_to_csv(parquet_files, output_file)

        print(f"Successfully converted {total_rows} rows from {len(parquet_files)} parquet file(s)")
        print(f"Output saved to: {os.path.abspath(output_file)}")

    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
