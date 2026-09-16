import pyarrow.parquet as pq
import csv
import json

# === CONFIG ===
INPUT_PARQUET = "input.parquet"
OUTPUT_CSV = "output.csv"

# Column names in your Parquet file
COL_ANSWER = "answer"
COL_CONTEXT = "context"
COL_QUESTION = "question"
COL_START = "answer_start"

# === CONVERSION ===
table = pq.read_table(INPUT_PARQUET)

# Convert to Python dict batches (streaming-friendly)
batches = table.to_batches()

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["answer", "context", "question", "answer_start"])

    for batch in batches:
        data = batch.to_pydict()

        answers = data[COL_ANSWER]
        contexts = data[COL_CONTEXT]
        questions = data[COL_QUESTION]
        starts = data[COL_START]

        for a, c, q, s in zip(answers, contexts, questions, starts):
            # Ensure no nested JSON sneaks in
            if isinstance(a, dict): a = json.dumps(a)
            if isinstance(c, dict): c = json.dumps(c)
            if isinstance(q, dict): q = json.dumps(q)

            writer.writerow([a, c, q, s])