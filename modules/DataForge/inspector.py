def inspect_schema(df, filename):
    print(f"\n=== Schema for {filename} ===")
    print(df.dtypes)
    print("\nMissing values:")
    print(df.isna().sum())
    print("\nAverage lengths:")
    for col in ["question", "context", "answer"]:
        if col in df.columns:
            print(f"{col}: {df[col].astype(str).str.len().mean():.2f}")