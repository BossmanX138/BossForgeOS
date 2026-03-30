import psutil
import subprocess
import sys

def list_processes():
    for proc in psutil.process_iter(['pid', 'name']):
        print(f"PID: {proc.info['pid']}, Name: {proc.info['name']}")

def kill_process(pid):
    try:
        p = psutil.Process(pid)
        p.terminate()
        print(f"Process {pid} terminated.")
    except Exception as e:
        print(f"Error: {e}")

def start_process(command):
    try:
        subprocess.Popen(command, shell=True)
        print(f"Started: {command}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--kill', type=int)
    parser.add_argument('--start', type=str)
    args = parser.parse_args()
    if args.list:
        list_processes()
    elif args.kill:
        kill_process(args.kill)
    elif args.start:
        start_process(args.start)
    else:
        parser.print_help()
