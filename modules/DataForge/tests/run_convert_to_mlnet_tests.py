import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert_to_mlnet import convert_to_mlnet_format

sample = pd.DataFrame({"input":["What is 2+2?"],"output":["<think>hidden reasoning</think>4"]})
out = convert_to_mlnet_format(sample)
assert list(out.columns) == ["answer", "context", "question", "answer_index"]
assert out.loc[0, "question"] == "What is 2+2?"
assert out.loc[0, "answer"] == "4"
assert out.loc[0, "context"] == "hidden reasoning"
assert out.loc[0, "answer_index"] == 0
print('OK')
