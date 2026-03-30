import sys
import os
import argparse


def check_command_code(provided_code: str | None = None):
    try:
        code = None
        with open('command_code.txt', 'r', encoding='utf-8') as f:
            for line in f:
                candidate = line.strip()
                if candidate and not candidate.startswith('#'):
                    code = candidate
                    break
        if not code:
            print('No command code configured. Action aborted.')
            sys.exit(1)
        user_code = (provided_code or input('Enter command code: ').strip()).strip()
        if user_code != code:
            print('Invalid command code. Action aborted.')
            sys.exit(1)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

def perform_high_risk_action(action_func, *args, code: str | None = None, **kwargs):
    check_command_code(code)
    action_func(*args, **kwargs)

# Example usage:
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=str, default=None)
    args = parser.parse_args()

    def dangerous():
        print("High-risk action performed!")
    perform_high_risk_action(dangerous, code=args.code)
