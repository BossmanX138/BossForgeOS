import pandas as pd

TARGET_COLUMNS = ["question", "context", "answer", "answer_index"]

def validate_df(df, filename, log):
    bad_rows = []

    # First check for missing columns at DataFrame level (more efficient)
    missing_cols = [col for col in TARGET_COLUMNS if col not in df.columns]
    if missing_cols:
        log.write(f"{filename}: Missing required columns: {', '.join(missing_cols)}\n")
        return pd.DataFrame()

    # Check for rows with missing values
    for field in TARGET_COLUMNS:
        mask = df[field].isna()
        if mask.any():
            bad_rows.extend(df.index[mask])
            log.write(f"{filename}: Missing field {field} in rows: {', '.join(map(str, df.index[mask]))}\n")

    # Validate answer_index for all rows that have it
    if "answer_index" in df.columns:
        ai_mask = df["answer_index"].notna()
        if ai_mask.any():
            # Check numeric type
            non_numeric = (~df.loc[ai_mask, "answer_index"].apply(lambda x: isinstance(x, (int, float))))
            bad_rows.extend(df.index[ai_mask & non_numeric])
            log.write(f"{filename}: answer_index must be numeric in rows: {', '.join(map(str, df.index[ai_mask & non_numeric]))}\n")

    # Return DataFrame with bad rows removed
    if bad_rows:
        return df.drop(bad_rows).copy()
    return df.copy()