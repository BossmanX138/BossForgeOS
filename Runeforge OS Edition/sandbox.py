import os
import sys
import re

# Sandbox and Safety Enforcement for WindowsWorld Agent
# This script is intended to be imported and used by other scripts to enforce safety constraints.

# 1. Restrict file operations to whitelisted directories
WHITELISTED_DIRS = [
    os.path.abspath('C:/AgentSandbox'),
    os.path.abspath('C:/Temp'),
    os.path.abspath(os.getcwd()),
]

def is_path_safe(path):
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(wd) for wd in WHITELISTED_DIRS)

# 2. Block dangerous registry keys and system settings
DANGEROUS_REG_KEYS = [
    r'HKEY_LOCAL_MACHINE\\SYSTEM',
    r'HKEY_LOCAL_MACHINE\\SAM',
    r'HKEY_LOCAL_MACHINE\\SECURITY',
    r'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run',
]

def is_registry_key_safe(key_path):
    for danger in DANGEROUS_REG_KEYS:
        if key_path.upper().startswith(danger.upper()):
            return False
    return True

# 3. Redact sensitive data from observations
SENSITIVE_PATTERNS = [
    r'password', r'api[_-]?key', r'secret', r'token', r'credential', r'private', r'license',
]

def redact_sensitive(text):
    for pat in SENSITIVE_PATTERNS:
        text = re.sub(pat, '[REDACTED]', text, flags=re.IGNORECASE)
    return text

# 4. VM/Environment check (basic)
def is_running_in_vm():
    try:
        import wmi
        c = wmi.WMI()
        for sys in c.Win32_ComputerSystem():
            if sys.Manufacturer.lower().find('vmware') != -1 or sys.Model.lower().find('virtual') != -1:
                return True
    except Exception:
        pass
    return False

if __name__ == "__main__":
    print("Sandbox module loaded. Import and use in other scripts.")
