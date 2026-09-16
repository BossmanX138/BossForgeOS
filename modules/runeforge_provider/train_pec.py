import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)


PERSONA_RULES = [
    ("refusal", {"refusal", "safety_refusal", "guardrail"}),
    ("activist", {"activist", "activism"}),
    ("daughter", {"daughter", "protector_daughter"}),
    ("mentor", {"mentor", "guidance"}),
    ("coder", {"coder", "code", "debug", "debugging", "refactor", "engineering", "fix", "optimize", "clean"}),
    ("mythic", {"mythic", "mythos", "ritual", "founder"}),
    ("serene", {"serene", "tone_calm"}),
    ("builder", {"system_design", "architecture", "build", "python_service", "frontend", "ci"}),
]

TONE_RULES = [
    ("calm", {"tone_calm", "serene", "reassuring"}),
    ("sassy", {"default_sassy", "sassy"}),
    ("mythic", {"mythic", "mythos", "ritual"}),
    ("focused", {"coder", "debug", "debugging", "engineering", "refactor", "fix", "optimize"}),
    ("firm", {"refusal", "guardrail", "safety_refusal"}),
    ("mentor", {"thoughtful", "guidance"}),
]

EMOTION_RULES = [
    ("protective", {"protective", "guardian", "guardrail", "refusal", "safety_refusal"}),
    ("reassuring", {"mentor", "serene", "tone_calm", "guidance", "thoughtful"}),
    ("analytical", {"coder", "debug", "debugging", "engineering", "refactor", "fix", "optimize", "clean"}),
    ("evocative", {"mythic", "mythos", "ritual"}),
    ("encouraging", {"activist", "uplift"}),
]

INTENSITY_RULES = [
    ("high", {"urgent", "protective", "activist", "refusal", "safety_refusal"}),
    ("medium", {"sassy", "mythic", "mentor", "coder", "debugging", "refactor", "system_design"}),
]


def select_bucket(tags: set, rules: List[Tuple[str, set]], default_value: str) -> str:
    for value, keys in rules:
        if tags.intersection(keys):
            return value
    return default_value


def build_control_label(tags: List[str], mode: str) -> str:
    norm_tags = {t.strip().lower() for t in tags if t and isinstance(t, str)}
    if mode:
        norm_tags.add(str(mode).strip().lower())
    persona = select_bucket(norm_tags, PERSONA_RULES, "builder")
    tone = select_bucket(norm_tags, TONE_RULES, "calm")
    emotion = select_bucket(norm_tags, EMOTION_RULES, "focused")
    intensity = select_bucket(norm_tags, INTENSITY_RULES, "low")
    return f"{persona}|{tone}|{emotion}|{intensity}"


def build_persona_label(tags: List[str], mode: str) -> str:
    norm_tags = {t.strip().lower() for t in tags if t and isinstance(t, str)}
    if mode:
        norm_tags.add(str(mode).strip().lower())
    # Explicit tag-first overrides from current corpus signal.
    if "sassy" in norm_tags:
        return "builder"
    if "thoughtful" in norm_tags:
        return "mentor"
    if "fix" in norm_tags or "optimize" in norm_tags or "clean" in norm_tags:
        return "coder"
    if "system_design" in norm_tags:
        return "builder"
    return select_bucket(norm_tags, PERSONA_RULES, "builder")


def read_jsonl(path: Path, limit: int, seed: int, label_mode: str) -> List[Dict]:
    rows: List[Dict] = []
    rng = random.Random(seed)
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            obj = json.loads(line)
            inst = (obj.get("instruction") or "").strip()
            inp = (obj.get("input") or "").strip()
            meta = obj.get("metadata") or {}
            tags = meta.get("tags") or []
            mode = meta.get("mode") or ""
            if label_mode == "persona":
                label = build_persona_label(tags, mode)
            else:
                label = build_control_label(tags, mode)
            text = inst if not inp else f"{inst}\nContext: {inp}"
            rows.append({"text": text, "label_text": label})
            if limit > 0 and len(rows) >= limit:
                break
            if idx > 0 and idx % 200000 == 0 and limit <= 0:
                # If full dataset requested, keep memory bounded by light downsample for practicality.
                rows = rng.sample(rows, k=min(len(rows), 180000))
    return rows


def balance_rows(
    rows: List[Dict], min_per_label: int, max_per_label: int, seed: int
) -> List[Dict]:
    by_label: Dict[str, List[Dict]] = {}
    for r in rows:
        by_label.setdefault(r["label_text"], []).append(r)

    rng = random.Random(seed)
    balanced: List[Dict] = []
    for label, items in by_label.items():
        if len(items) < min_per_label:
            continue
        rng.shuffle(items)
        take = min(len(items), max_per_label)
        balanced.extend(items[:take])
    rng.shuffle(balanced)
    return balanced


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model_name", default="distilbert-base-uncased")
    parser.add_argument("--output_dir", default="pec_model")
    parser.add_argument("--max_samples", type=int, default=120000)
    parser.add_argument("--num_train_epochs", type=float, default=1.5)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--label_mode", choices=["composite", "persona"], default="composite")
    parser.add_argument("--min_per_label", type=int, default=100)
    parser.add_argument("--max_per_label", type=int, default=10000)
    parser.add_argument("--max_length", type=int, default=128)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    dataset_path = Path(args.dataset)
    rows = read_jsonl(dataset_path, args.max_samples, args.seed, args.label_mode)
    if len(rows) < 500:
        raise RuntimeError("Not enough samples found to train PEC.")

    rows = balance_rows(rows, args.min_per_label, args.max_per_label, args.seed)
    if len(rows) < 500:
        raise RuntimeError("Not enough balanced samples after label filtering.")

    label_counts = Counter(r["label_text"] for r in rows)
    labels = sorted(label_counts.keys())
    label2id = {label: i for i, label in enumerate(labels)}
    id2label = {i: label for label, i in label2id.items()}

    for row in rows:
        row["label"] = label2id[row["label_text"]]

    random.shuffle(rows)
    split = int(len(rows) * 0.95)
    train_rows = rows[:split]
    eval_rows = rows[split:]

    train_ds = Dataset.from_list(train_rows)
    eval_ds = Dataset.from_list(eval_rows)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    def preprocess(examples: Dict) -> Dict:
        return tokenizer(examples["text"], truncation=True, max_length=args.max_length)

    train_ds = train_ds.map(preprocess, batched=True)
    eval_ds = eval_ds.map(preprocess, batched=True)
    train_ds = train_ds.remove_columns(["text", "label_text"])
    eval_ds = eval_ds.remove_columns(["text", "label_text"])

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(labels),
        id2label=id2label,
        label2id=label2id,
    )

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    train_args = TrainingArguments(
        output_dir=str(Path(args.output_dir) / "checkpoints"),
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.num_train_epochs,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.03,
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=200,
        save_steps=400,
        save_total_limit=1,
        fp16=False,
        seed=args.seed,
        report_to=[],
    )

    def compute_metrics(eval_pred) -> Dict[str, float]:
        logits, labels_np = eval_pred
        preds = np.argmax(logits, axis=-1)
        acc = float((preds == labels_np).mean())
        return {"accuracy": acc}

    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        processing_class=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    metrics = trainer.evaluate()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    stats = {
        "samples_total": len(rows),
        "samples_train": len(train_rows),
        "samples_eval": len(eval_rows),
        "num_labels": len(labels),
        "top_labels": label_counts.most_common(15),
        "eval_metrics": metrics,
        "base_model": args.model_name,
        "label_mode": args.label_mode,
    }
    (out_dir / "pec_training_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
