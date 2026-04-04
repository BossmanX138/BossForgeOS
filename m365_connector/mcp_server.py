import os
from flask import Flask, request, jsonify
from msal import ConfidentialClientApplication

app = Flask(__name__)

# Load config from environment or config file
tenant_id = os.getenv('M365_TENANT_ID', 'YOUR_TENANT_ID')
client_id = os.getenv('M365_CLIENT_ID', 'YOUR_CLIENT_ID')
client_secret = os.getenv('M365_CLIENT_SECRET', 'YOUR_CLIENT_SECRET')
redirect_uri = os.getenv('M365_REDIRECT_URI', 'http://localhost:5000/callback')

SCOPES = [
    'https://graph.microsoft.com/.default',
    'offline_access',
]

msal_app = ConfidentialClientApplication(
    client_id,
    authority=f'https://login.microsoftonline.com/{tenant_id}',
    client_credential=client_secret
)

def get_token():
    result = msal_app.acquire_token_for_client(scopes=SCOPES)
    if 'access_token' in result:
        return result['access_token']
    raise Exception(f"Token error: {result}")

@app.route('/mcp/action', methods=['POST'])
def handle_action():
    data = request.json or {}
    action = data.get('action')
    params = data.get('params', {})
    # Route to action handlers
    if action == 'outlook_read_mail':
        from actions.outlook import read_mail
        return jsonify(read_mail(get_token(), params))
    if action == 'teams_post_message':
        from actions.teams import post_message
        return jsonify(post_message(get_token(), params))
    if action == 'onedrive_list_files':
        from actions.onedrive import list_files
        return jsonify(list_files(get_token(), params))
    if action == 'onenote_list_notebooks':
        from actions.onenote import list_notebooks
        return jsonify(list_notebooks(get_token(), params))
    if action == 'access_query':
        from actions.access import query_db
        return jsonify(query_db(get_token(), params))
    return jsonify({'error': 'Unknown action'}), 400

if __name__ == '__main__':
    app.run(port=5000)
