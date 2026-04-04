# Microsoft 365 Connector Agent Setup

## Azure AD App Registration
1. Go to Azure Portal > Azure Active Directory > App registrations > New registration.
2. Name: `BossForgeOS M365 Connector`
3. Redirect URI: `http://localhost:5000/callback`
4. After creation, note the Application (client) ID and Directory (tenant) ID.
5. Certificates & secrets: Create a new client secret and note the value.
6. API permissions:
   - Microsoft Graph > Delegated permissions:
     - Mail.Read, Mail.Send
     - Files.Read, Files.ReadWrite
     - Notes.Read, Notes.ReadWrite
     - User.Read
     - ChannelMessage.Send, ChannelMessage.Read.All
     - Sites.Read.All
   - Grant admin consent.

## Environment Variables
Set the following environment variables or update in `mcp_server.py`:
- `M365_TENANT_ID`
- `M365_CLIENT_ID`
- `M365_CLIENT_SECRET`
- `M365_REDIRECT_URI`

## Running the Agent
```
pip install -r requirements.txt
python mcp_server.py
```

## Extending
- Add new action handlers in `actions/`
- Register new actions in `mcp_server.py`
