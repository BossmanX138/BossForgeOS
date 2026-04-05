import os
import sys
import json
import base64
from cryptography.fernet import Fernet, InvalidToken

# --- Licensing/Decryption ---
def load_license(license_path):
    try:
        with open(license_path, 'r') as f:
            lic = json.load(f)
        return lic.get('key')
    except Exception:
        return None

def decrypt_agent(agent_path, key):
    try:
        with open(agent_path, 'rb') as f:
            encrypted = f.read()
        fernet = Fernet(key.encode())
        decrypted = fernet.decrypt(encrypted)
        return decrypted
    except InvalidToken:
        print('Invalid license or agent file.')
        return None
    except Exception as e:
        print('Error:', e)
        return None

def show_model_card(agent_path):
    # Model card is always visible (unencrypted JSON at start of file)
    try:
        with open(agent_path, 'rb') as f:
            header = f.read(4096).decode(errors='ignore')
            if header.startswith('{'):
                end = header.find('}\n')
                if end != -1:
                    card = header[:end+1]
                    print('Model Card:', card)
                    return
    except Exception:
        pass
    print('No model card found.')

# --- vLLM Integration (placeholder) ---
def run_agent_with_vllm(agent_bytes):
    # In a real system, this would load the model into vLLM and run inference
    print('Running agent with vLLM... (stub)')
    # ...

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='vLLM Secure Agent Runner')
    parser.add_argument('--agent', required=True, help='Path to encrypted agent file')
    parser.add_argument('--license', required=False, help='Path to license file (JSON with key)')
    parser.add_argument('--show-card', action='store_true', help='Show model card only')
    args = parser.parse_args()

    if args.show_card:
        show_model_card(args.agent)
        sys.exit(0)

    key = None
    if args.license:
        key = load_license(args.license)
    else:
        print('No license provided. Cannot run agent.')
        sys.exit(1)

    agent_bytes = decrypt_agent(args.agent, key)
    if agent_bytes:
        run_agent_with_vllm(agent_bytes)
    else:
        print('Failed to run agent.')
