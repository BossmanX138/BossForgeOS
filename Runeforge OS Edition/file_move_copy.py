
import shutil
import os

# Example paths (change as needed for your VM)
src = r"C:\AgentSandbox\example.txt"
dst_copy = r"C:\AgentSandbox\copy_example.txt"
dst_move = r"C:\AgentSandbox\moved_example.txt"

# Ensure source file exists for demo
if not os.path.exists(src):
    with open(src, 'w') as f:
        f.write("This is a test file.")

# Read command code from config
def get_command_code():
    with open("command_code.txt", "r") as f:
        for line in f:
            code = line.strip()
            if code and not code.startswith('#'):
                return code
    return None

def require_code():
    code = get_command_code()
    user = input(f"Enter your command code to proceed: ")
    if user.strip() != code:
        print("Incorrect code. Action aborted.")
        exit(1)

# Copy file (high risk)
print(f"About to copy {src} to {dst_copy}")
require_code()
shutil.copy(src, dst_copy)
print(f"Copied {src} to {dst_copy}")

# Move file (high risk)
print(f"About to move {src} to {dst_move}")
require_code()
shutil.move(src, dst_move)
print(f"Moved {src} to {dst_move}")
