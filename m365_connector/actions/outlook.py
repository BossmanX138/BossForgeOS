import requests

def read_mail(token, params):
    headers = {'Authorization': f'Bearer {token}'}
    url = 'https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages'
    resp = requests.get(url, headers=headers)
    if resp.ok:
        return resp.json()
    return {'error': resp.text}
