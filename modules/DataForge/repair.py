import pandas as pd

def repair_answer_index(df):
    """
    More efficient version of answer index repair using vectorized operations.
    This avoids the slow iterrows() approach and uses string methods directly.
    """
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()

    # Vectorized operation for finding answer in context
    mask = (df['answer'].notna()) & (df['context'].notna()) & (df['answer_index'].isna())
    if mask.any():
        # Use str.find() which returns -1 if not found, then convert to NaN
        find_results = df.loc[mask, 'context'].str.find(df.loc[mask, 'answer'])
        valid_indices = find_results >= 0
        df.loc[mask & valid_indices, 'answer_index'] = find_results[valid_indices]

    return df

# Example usage:
# df = repair_answer_index(df)