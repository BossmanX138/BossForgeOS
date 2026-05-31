import pandas as pd

def repair_answer_index(df):
    """
    More efficient version of answer index repair.
    Uses vectorized operations instead of iterrows.
    """
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()

    # Find rows where answer_index is missing but answer and context exist
    mask = (
        pd.isna(df["answer_index"]) &
        (~pd.isna(df["answer"])) &
        (~pd.isna(df["context"]))
    )

    if mask.any():
        # Vectorized operation to find answer positions
        answers = df.loc[mask, "answer"].astype(str)
        contexts = df.loc[mask, "context"].astype(str)

        # Find positions using str.find (vectorized)
        positions = contexts.str.find(answers)

        # Update only the rows where we found a position
        df.loc[positions >= 0, "answer_index"] = positions[positions >= 0]

    return df