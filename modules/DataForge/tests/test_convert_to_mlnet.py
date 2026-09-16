import pandas as pd
from pathlib import Path
import sys

MODULE_DIR = Path(__file__).resolve().parents[1]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from convert_to_mlnet import convert_to_mlnet_format, strip_think_block


def test_maps_input_output_and_strips_think():
    df = pd.DataFrame(
        {
            "input": ["What is 2+2?"],
            "output": ["<think>hidden</think>4"],
        }
    )

    out = convert_to_mlnet_format(df)

    assert list(out.columns) == ["answer", "context", "question", "answer_index"]
    assert out.loc[0, "question"] == "What is 2+2?"
    assert out.loc[0, "answer"] == "4"
    assert out.loc[0, "context"] == ""
    assert out.loc[0, "answer_index"] == 0


def test_strip_think_block_without_tag_keeps_text():
    assert strip_think_block("plain answer") == "plain answer"
