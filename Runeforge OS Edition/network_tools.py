import socket
import os
import subprocess

def get_ip():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    print(f"IP Address: {ip}")

def check_connectivity(host="8.8.8.8"):
    response = os.system(f"ping -n 1 {host}")
    if response == 0:
        print(f"Connected to {host}")
    else:
        print(f"Cannot reach {host}")

def list_wifi():
    result = subprocess.run(["netsh", "wlan", "show", "networks"], capture_output=True, text=True)
    print(result.stdout)

if __name__ == "__main__":
    get_ip()
    check_connectivity()
    list_wifi()
