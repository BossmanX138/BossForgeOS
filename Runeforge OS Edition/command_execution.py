import subprocess
import sys

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Error:", result.stderr)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', type=str, nargs='+', help='Command to run')
    args = parser.parse_args()
    run_command(' '.join(args.command))
