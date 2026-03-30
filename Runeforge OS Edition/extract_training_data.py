import os
import json
import argparse

# Script to extract (observation, action) pairs from episode logs for training

def extract_pairs_from_log(log_path):
    pairs = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                obs = entry.get('observation')
                action = entry.get('action')
                if obs is not None and action is not None:
                    pairs.append({'observation': obs, 'action': action})
            except Exception as e:
                print(f"Error parsing line in {log_path}: {e}")
    return pairs

def main(input_dir, output_file):
    all_pairs = []
    for fname in os.listdir(input_dir):
        if fname.endswith('.jsonl'):
            log_path = os.path.join(input_dir, fname)
            pairs = extract_pairs_from_log(log_path)
            all_pairs.extend(pairs)
    with open(output_file, 'w', encoding='utf-8') as out:
        for pair in all_pairs:
            out.write(json.dumps(pair, ensure_ascii=False) + '\n')
    print(f"Extracted {len(all_pairs)} (observation, action) pairs to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract (observation, action) pairs from episode logs.")
    parser.add_argument('--input_dir', type=str, required=True, help='Directory containing JSONL episode logs')
    parser.add_argument('--output_file', type=str, required=True, help='Output file for training data (JSONL)')
    args = parser.parse_args()
    main(args.input_dir, args.output_file)
