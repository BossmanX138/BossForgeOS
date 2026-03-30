# Fine-Tuning and Training Pipeline for WindowsWorld Agent

This document describes how to convert logged episodes into training datasets for supervised learning and reinforcement learning.

## Table of Contents

- [Episode Logging](#episode-logging)
- [Data Extraction Script](#data-extraction-script)
- [Training and Fine-Tuning](#training-and-fine-tuning)
- [Example Usage](#example-usage)
- [Notes](#notes)

## Episode Logging

- Each interaction is logged as JSONL.
- Each line includes:
  - `observation`: Agent observation (state, UIA tree, OCR, and more).
  - `action`: Action taken by the agent (from `action_schema.json`).
  - `reward` (optional): Reward signal for RL.
  - `info` (optional): Additional metadata.

## Data Extraction Script

- Use `extract_training_data.py` to process episode logs.
- The script can:
  - Read all JSONL episode files in the workspace.
  - Extract observation/action pairs.
  - Optionally filter or preprocess (for example redact sensitive data).
  - Output training data in JSONL, CSV, or other formats.

## Training and Fine-Tuning

- The extracted dataset can support:
  - Supervised learning: Predict actions from observations.
  - Reinforcement learning: Use reward signals with RL algorithms.
- Training scripts or notebooks can be added as needed (PyTorch, TensorFlow, HuggingFace, and others).

## Example Usage

```bash
python extract_training_data.py --input_dir ./logs --output_file training_data.jsonl
```

## Notes

- Ensure logs are comprehensive and anonymized as needed.
- For RL, ensure reward signals are present.
- See `extract_training_data.py` for customization options.
