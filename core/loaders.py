import duckdb
import pandas as pd
import json
import yaml
from pathlib import Path

def detect_format(path):
    ext = Path(path).suffix.lower()
    return {
        ".parquet": "parquet",
        ".jsonl": "jsonl",
        ".json": "json",
        ".csv": "csv",
        ".yml": "yaml",
        ".yaml": "yaml"
    }.get(ext, None)

def load_any(path):
    fmt = detect_format(path)
    if not fmt:
        print(f"Unknown file format for {path}")
        return None
    try:
        return LOADERS[fmt](path)
    except Exception as e:
        print(f"Error loading file {path}: {str(e)}")
        return pd.DataFrame()