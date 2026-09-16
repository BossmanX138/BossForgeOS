import os
import pandas as pd
from .validators import validate_df, TARGET_COLUMNS

class DataForge:
    def __init__(self, input_dir, output_dir, log):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.log = log
        self.TARGET_COLUMNS = TARGET_COLUMNS  # Use the same columns as validators
        # Default ML.NET format configuration - completed
        self.mlnet_format = {
            "question": {"name": "Question", "type": "string"},
            "context": {"name": "Context", "type": "string"},
            "answer": {"name": "Answer", "type": "string"},
            "answer_index": {"name": "AnswerStartPosition", "type": "int"}
        }

    def process_all(self):
        files = [f for f in os.listdir(self.input_dir) if os.path.isfile(os.path.join(self.input_dir, f))]
        merged = pd.DataFrame()

        for file in files:
            try:
                df = self._load_and_validate(file)
                if not df.empty:
                    # Only keep the merged DataFrame in memory, no intermediate files
                    merged = pd.concat([merged, df], ignore_index=True)
            except Exception as e:
                self.log.write(f"Error processing {file}: {str(e)}\n")

        return merged

    def _load_and_validate(self, file):
        from .loaders import load_any
        path = os.path.join(self.input_dir, file)
        df = load_any(path)

        if df is not None:
            validated_df = validate_df(df, file, self.log)
            # Ensure validate_df returns a valid DataFrame
            if validated_df is not None and not validated_df.empty:
                # Ensure all target columns exist with appropriate default values
                for col in self.TARGET_COLUMNS:
                    if col not in validated_df.columns:
                        # Use appropriate default based on expected type
                        if "type" in self.mlnet_format.get(col, {}):
                            col_type = self.mlnet_format[col]["type"]
                            if col_type == "int":
                                validated_df[col] = 0
                            elif col_type == "string":
                                validated_df[col] = ""
                            else:
                                validated_df[col] = ""
                        else:
                            validated_df[col] = ""
                return validated_df
        return pd.DataFrame()

    def get_mlnet_format(self):
        """Return the ML.NET format configuration."""
        return self.mlnet_format