import argparse
import json

# Action Sequence Executor
# Accepts a JSON file or string with a list of actions and executes them in order

def execute_action(action):
    # This should call the command processor or dispatch to the correct script.
    # For demo, just print
    print(f"Executing: {action}")
    # ...existing code to dispatch actions...


def execute_sequence(actions):
    for action in actions:
        execute_action(action)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str, help='JSON file with action sequence')
    parser.add_argument('--json', type=str, help='JSON string with action sequence')
    args = parser.parse_args()
    if args.file:
        with open(args.file, 'r') as f:
            actions = json.load(f)
        execute_sequence(actions)
    elif args.json:
        actions = json.loads(args.json)
        execute_sequence(actions)
    else:
        print("Provide --file or --json with action sequence.")
