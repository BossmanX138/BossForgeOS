import requests

def post_message(token, params):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    team_id = params.get('team_id')
    channel_id = params.get('channel_id')
    message = params.get('message', 'Hello from MCP!')
    url = f'https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages'
    data = {'body': {'content': message}}
    resp = requests.post(url, headers=headers, json=data)
    if resp.ok:
        return resp.json()
    return {'error': resp.text}
