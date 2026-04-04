import os
from flask import Flask, request, jsonify
from actions import outlook, teams, onedrive, calendar

app = Flask(__name__)

REQUIRED_ENV = [
    'M365_TENANT_ID',
    'M365_CLIENT_ID',
    'M365_CLIENT_SECRET',
    'M365_MAILBOX_USER',
]

# MCP tool registry
tools = {
    'readEmail': outlook.read_email,
    'sendEmail': outlook.send_email,
    'getCalendarEvents': calendar.get_events,
    'sendTeamsMessage': teams.send_message,
    'readTeamsMessages': teams.read_messages,
    'onedriveListFiles': onedrive.list_files,
    'onedriveDownloadFile': onedrive.download_file,
    'onedriveUploadFile': onedrive.upload_file,
}

@app.route('/mcp/tool', methods=['POST'])
def mcp_tool():
    data = request.json
    tool = data.get('tool')
    params = data.get('params', {})
    if tool in tools:
        try:
            result = tools[tool](**params)
            return jsonify({'result': result})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Unknown tool'}), 400


@app.route('/health', methods=['GET'])
def health():
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    return jsonify(
        {
            'status': 'ok' if not missing else 'degraded',
            'missingEnv': missing,
            'tools': sorted(tools.keys()),
        }
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
