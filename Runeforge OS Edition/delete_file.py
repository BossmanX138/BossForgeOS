
import os

# Path to file to delete (change as needed)
target = r"C:\AgentSandbox\delete_me.txt"

# Ensure file exists for demo
if not os.path.exists(target):
    with open(target, 'w') as f:
        f.write("This file will be deleted.")

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
    user = input(f"Enter your command code to confirm deletion: ")
    if user.strip() != code:
        print("Incorrect code. File not deleted.")
        exit(1)

print(f"About to delete {target}")
require_code()
os.remove(target)
print(f"{target} deleted.")
