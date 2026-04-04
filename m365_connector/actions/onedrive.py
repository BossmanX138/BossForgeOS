import requests

def list_files(token, params):
    headers = {'Authorization': f'Bearer {token}'}
    url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
    resp = requests.get(url, headers=headers)
    if resp.ok:
        return resp.json()
    return {'error': resp.text}
